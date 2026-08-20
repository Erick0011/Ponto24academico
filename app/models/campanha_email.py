from datetime import datetime
from app import db


class CampanhaEmail(db.Model):
    """Campanha de email em massa (marketing) enviada pelo admin."""

    __tablename__ = "campanhas_email"

    PUBLICO_TODOS = "todos"
    PUBLICO_CONFIRMADOS = "confirmados"
    PUBLICO_ATIVOS = "ativos"

    ESTADO_RASCUNHO = "rascunho"
    ESTADO_ENVIANDO = "enviando"
    ESTADO_PAUSADA = "pausada_limite_diario"
    ESTADO_CONCLUIDA = "concluida"
    ESTADO_CANCELADA = "cancelada"

    id = db.Column(db.Integer, primary_key=True)
    assunto = db.Column(db.String(200), nullable=False)
    corpo_html = db.Column(db.Text, nullable=False)
    publico = db.Column(db.String(30), nullable=False, default=PUBLICO_TODOS)
    estado = db.Column(db.String(30), nullable=False, default=ESTADO_RASCUNHO, index=True)

    total_destinatarios = db.Column(db.Integer, default=0, nullable=False)
    enviados = db.Column(db.Integer, default=0, nullable=False)
    falhados = db.Column(db.Integer, default=0, nullable=False)

    enviados_hoje = db.Column(db.Integer, default=0, nullable=False)
    data_ultimo_envio = db.Column(db.Date, nullable=True)

    criado_por_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    iniciado_em = db.Column(db.DateTime, nullable=True)
    concluido_em = db.Column(db.DateTime, nullable=True)

    criado_por = db.relationship("User", foreign_keys=[criado_por_id])
    destinatarios = db.relationship(
        "CampanhaEmailDestinatario", back_populates="campanha",
        lazy="dynamic", cascade="all, delete-orphan",
    )

    @property
    def pendentes_count(self) -> int:
        return self.destinatarios.filter_by(estado="pendente").count()

    @property
    def progresso_pct(self) -> int:
        if not self.total_destinatarios:
            return 0
        return int((self.enviados + self.falhados) / self.total_destinatarios * 100)

    def __repr__(self):
        return f"<CampanhaEmail {self.id} '{self.assunto}' [{self.estado}]>"


class CampanhaEmailDestinatario(db.Model):
    """Uma linha por destinatário de uma campanha — permite retomar envios
    parciais (limite diário, reinício do servidor) sem duplicar envios."""

    __tablename__ = "campanha_email_destinatarios"
    __table_args__ = (
        db.UniqueConstraint("campanha_id", "utilizador_id", name="uq_campanha_utilizador"),
    )

    id = db.Column(db.Integer, primary_key=True)
    campanha_id = db.Column(db.Integer, db.ForeignKey("campanhas_email.id"), nullable=False, index=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    estado = db.Column(db.String(20), default="pendente", nullable=False, index=True)  # pendente, enviado, falhado
    enviado_em = db.Column(db.DateTime, nullable=True)
    erro = db.Column(db.Text, nullable=True)

    campanha = db.relationship("CampanhaEmail", back_populates="destinatarios")
    utilizador = db.relationship("User")
