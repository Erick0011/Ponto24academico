import uuid
from datetime import datetime
from app import db


class VisitaLog(db.Model):
    """Registo de tráfego da plataforma — mesmo de visitantes sem conta.

    Propositadamente minimalista por privacidade: guarda um identificador
    aleatório (sem qualquer dado pessoal), o caminho visitado e, se a pessoa
    estiver autenticada, o seu user_id. Nunca guarda IP nem user-agent — ver
    app/templates/main/privacidade.html, secção "Cookies"."""

    __tablename__ = "visita_log"

    id = db.Column(db.Integer, primary_key=True)
    sessao_id = db.Column(db.String(36), nullable=False, index=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    caminho = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    utilizador = db.relationship("User")

    def __repr__(self):
        return f"<VisitaLog {self.caminho} sessao={self.sessao_id[:8]}>"


def novo_sessao_id() -> str:
    return str(uuid.uuid4())
