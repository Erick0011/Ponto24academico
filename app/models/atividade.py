from datetime import datetime
from app import db


class AtividadeLog(db.Model):
    """Log de auditoria — regista eventos/movimentos da plataforma para o KPI."""

    __tablename__ = "atividade_log"

    # Materiais
    EVENTO_MATERIAL_APROVADO = "material_aprovado"
    EVENTO_MATERIAL_REJEITADO = "material_rejeitado"
    EVENTO_MATERIAL_SUBMETIDO = "material_submetido"

    # Pastas
    EVENTO_PASTA_CRIADA = "pasta_criada"
    EVENTO_MATERIAL_MOVIDO_PASTA = "material_movido_pasta"

    # Candidaturas
    EVENTO_CANDIDATURA_RECEBIDA = "candidatura_recebida"
    EVENTO_CANDIDATURA_APROVADA = "candidatura_aprovada"
    EVENTO_CANDIDATURA_REJEITADA = "candidatura_rejeitada"

    # Utilizadores / admin
    EVENTO_USER_PROMOVIDO_ADMIN = "user_promovido_admin"
    EVENTO_USER_REMOVIDO_ADMIN = "user_removido_admin"
    EVENTO_USER_PROMOVIDO_MODERADOR = "user_promovido_moderador"
    EVENTO_USER_REMOVIDO_MODERADOR = "user_removido_moderador"
    EVENTO_USER_ATIVADO = "user_ativado"
    EVENTO_USER_DESATIVADO = "user_desativado"
    EVENTO_CONTA_ELIMINADA = "conta_eliminada"  # autoserviço, Definições > Eliminar conta

    # Autenticação
    EVENTO_LOGIN = "login"
    EVENTO_LOGIN_FALHADO = "login_falhado"
    EVENTO_LOGOUT = "logout"
    EVENTO_REGISTO = "registo"

    # Conteúdo / lista de espera
    EVENTO_DOWNLOAD = "download"
    EVENTO_LISTA_ESPERA = "lista_espera_entrada"
    EVENTO_CONVITE_ENVIADO = "convite_enviado"

    # Marketing / email em massa
    EVENTO_CAMPANHA_CRIADA = "campanha_criada"
    EVENTO_CAMPANHA_ENVIADA = "campanha_enviada"
    EVENTO_CAMPANHA_CANCELADA = "campanha_cancelada"
    EVENTO_MARKETING_CANCELADO = "marketing_cancelado"  # utilizador cancelou subscrição

    id = db.Column(db.Integer, primary_key=True)
    evento = db.Column(db.String(40), nullable=False, index=True)
    # Alvo polimórfico opcional (material, candidatura, user, lista_espera...) — sem FK,
    # pois aponta para tabelas diferentes consoante o evento.
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    alvo_tipo = db.Column(db.String(40), nullable=True)
    alvo_id = db.Column(db.Integer, nullable=True)
    detalhes = db.Column(db.Text, nullable=True)  # JSON-encoded, contexto extra
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    utilizador = db.relationship("User", foreign_keys=[utilizador_id])

    def __repr__(self):
        return f"<AtividadeLog [{self.evento}] user={self.utilizador_id} alvo={self.alvo_tipo}:{self.alvo_id}>"
