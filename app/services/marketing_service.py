"""Envio de campanhas de email em massa (marketing) com proteções contra
bloqueio pelo servidor SMTP:

  1. Throttle — intervalo mínimo entre envios (MARKETING_INTERVALO_SEGUNDOS).
  2. Limite diário — nunca envia mais que MARKETING_LIMITE_DIARIO num único
     dia; o resto fica pendente e retoma no dia seguinte (ou quando o admin
     clicar em "Continuar").
  3. Envio a uma linha por destinatário (CampanhaEmailDestinatario) — se o
     processo for interrompido a meio (reinício do servidor, erro), o envio
     retoma exatamente de onde ficou, sem duplicar mensagens já enviadas.
  4. Só envia a quem tem `aceita_marketing=True` e conta ativa — respeita
     cancelamentos de subscrição.
  5. Delega a construção do email (headers List-Unsubscribe, versão texto
     simples, etc.) a `mail_service.enviar_email_marketing`.

Executado em segundo plano numa thread simples (sem dependências externas
tipo Celery/Redis) para não bloquear o pedido HTTP do admin.
"""

import time
import logging
import threading
from datetime import datetime, date

from flask import render_template, url_for

from app import db
from app.models.user import User
from app.models.campanha_email import CampanhaEmail, CampanhaEmailDestinatario
from app.services.mail_service import enviar_email_marketing
from app.services.tokens_service import gerar_token
from app.services.atividade_service import registar_atividade
from app.models.atividade import AtividadeLog

logger = logging.getLogger(__name__)

SALT_MARKETING_CANCELAR = "cancelar-marketing"


def publico_query(publico: str):
    """Devolve a query de utilizadores elegíveis para o público escolhido.
    Em todos os casos: só contas ativas e que não cancelaram marketing."""
    q = User.query.filter_by(is_active=True, aceita_marketing=True)
    if publico == CampanhaEmail.PUBLICO_CONFIRMADOS:
        q = q.filter_by(email_verificado=True)
    elif publico == CampanhaEmail.PUBLICO_ATIVOS:
        q = q.filter(
            db.func.coalesce(User.total_downloads, 0) + db.func.coalesce(User.total_uploads, 0) > 0
        )
    return q


def preparar_destinatarios(campanha: CampanhaEmail):
    """Popula CampanhaEmailDestinatario (uma vez só, na primeira vez que a
    campanha é enviada). Idempotente — se já existirem linhas, não duplica."""
    if campanha.destinatarios.count() > 0:
        return
    utilizadores = publico_query(campanha.publico).all()
    for u in utilizadores:
        db.session.add(CampanhaEmailDestinatario(campanha_id=campanha.id, utilizador_id=u.id))
    campanha.total_destinatarios = len(utilizadores)
    db.session.commit()


def _link_cancelar(user: User) -> str:
    token = gerar_token(str(user.id), SALT_MARKETING_CANCELAR)
    return url_for("main.cancelar_marketing", token=token, _external=True)


def _corpo_final(campanha: CampanhaEmail, user: User) -> str:
    return render_template(
        "email/marketing_base.html",
        corpo_html=campanha.corpo_html,
        user=user,
        url_cancelar=_link_cancelar(user),
    )


def processar_fila(app, campanha_id: int, base_url: str):
    """Corre em thread própria. Envia destinatários pendentes respeitando o
    throttle e o limite diário; para automaticamente ao atingir o limite,
    ao esgotar a fila, ou se a campanha for cancelada entretanto.

    base_url: capturado de request.url_root no pedido HTTP que disparou o
    envio (ex: 'https://ponto24academico.com/') — a thread não tem um
    request real, por isso usa-se test_request_context(base_url=...) para
    que url_for(_external=True) construa o domínio correto em vez de falhar
    ou gerar 'http://localhost/'."""
    with app.app_context():
        campanha = CampanhaEmail.query.get(campanha_id)
        if not campanha:
            return

        intervalo = app.config.get("MARKETING_INTERVALO_SEGUNDOS", 3)
        limite_diario = app.config.get("MARKETING_LIMITE_DIARIO", 300)

        hoje = date.today()
        if campanha.data_ultimo_envio != hoje:
            campanha.enviados_hoje = 0
            campanha.data_ultimo_envio = hoje
        db.session.commit()

        while True:
            campanha = CampanhaEmail.query.get(campanha_id)
            if campanha.estado == CampanhaEmail.ESTADO_CANCELADA:
                logger.info("Campanha %s cancelada — a parar envio.", campanha_id)
                return

            hoje = date.today()
            if campanha.data_ultimo_envio != hoje:
                campanha.enviados_hoje = 0
                campanha.data_ultimo_envio = hoje
                db.session.commit()

            destino = (campanha.destinatarios
                       .filter_by(estado="pendente")
                       .order_by(CampanhaEmailDestinatario.id)
                       .first())

            # Só pausa por limite diário se ainda houver trabalho pendente —
            # caso contrário uma campanha cujo nº de destinatários coincide
            # exatamente com o limite ficaria presa em "pausada" para sempre.
            if destino and campanha.enviados_hoje >= limite_diario:
                campanha.estado = CampanhaEmail.ESTADO_PAUSADA
                db.session.commit()
                logger.info("Campanha %s atingiu o limite diário (%s) — pausada.",
                            campanha_id, limite_diario)
                return

            if not destino:
                campanha.estado = CampanhaEmail.ESTADO_CONCLUIDA
                campanha.concluido_em = datetime.utcnow()
                db.session.commit()
                registar_atividade(
                    AtividadeLog.EVENTO_CAMPANHA_ENVIADA,
                    utilizador_id=campanha.criado_por_id, alvo_tipo="campanha_email",
                    alvo_id=campanha.id,
                    detalhes={"assunto": campanha.assunto, "enviados": campanha.enviados,
                              "falhados": campanha.falhados},
                )
                db.session.commit()
                logger.info("Campanha %s concluída (%s enviados, %s falhados).",
                            campanha_id, campanha.enviados, campanha.falhados)
                return

            user = destino.utilizador
            try:
                if not user or not user.is_active or not user.aceita_marketing:
                    destino.estado = "falhado"
                    destino.erro = "Destinatário inelegível (inativo ou cancelou marketing)"
                else:
                    with app.test_request_context(base_url=base_url):
                        link_cancelar = _link_cancelar(user)
                        corpo = _corpo_final(campanha, user)
                    enviar_email_marketing(user.email, campanha.assunto, corpo, link_cancelar)
                    destino.estado = "enviado"
                    destino.enviado_em = datetime.utcnow()
                    campanha.enviados += 1
                    campanha.enviados_hoje += 1
            except Exception as e:
                destino.estado = "falhado"
                destino.erro = str(e)[:500]
                campanha.falhados += 1
                logger.warning("Falha ao enviar campanha %s para user %s: %s",
                                campanha_id, destino.utilizador_id, e)

            db.session.commit()
            time.sleep(intervalo)


def iniciar_envio(campanha: CampanhaEmail, app, base_url: str):
    """Prepara os destinatários (1ª vez) e arranca (ou retoma) a thread de envio."""
    preparar_destinatarios(campanha)
    campanha.estado = CampanhaEmail.ESTADO_ENVIANDO
    if not campanha.iniciado_em:
        campanha.iniciado_em = datetime.utcnow()
    db.session.commit()

    thread = threading.Thread(
        target=processar_fila, args=(app, campanha.id, base_url), daemon=True,
        name=f"campanha-{campanha.id}",
    )
    thread.start()
