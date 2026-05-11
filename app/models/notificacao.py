from datetime import datetime
from app import db


class Notificacao(db.Model):
    """Notificação in-app para um utilizador."""

    __tablename__ = "notificacoes"

    TIPO_MATERIAL_APROVADO  = "material_aprovado"
    TIPO_MATERIAL_REJEITADO = "material_rejeitado"
    TIPO_SISTEMA            = "sistema"

    id            = db.Column(db.Integer, primary_key=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tipo          = db.Column(db.String(40), nullable=False, default="sistema")
    titulo        = db.Column(db.String(200), nullable=False)
    mensagem      = db.Column(db.Text)
    url           = db.Column(db.String(300))
    lida          = db.Column(db.Boolean, default=False, nullable=False)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Notificacao [{self.tipo}] user={self.utilizador_id} lida={self.lida}>"
