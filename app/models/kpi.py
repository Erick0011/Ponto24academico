from datetime import datetime
from app import db


class PesquisaLog(db.Model):
    __tablename__ = "pesquisa_log"

    id            = db.Column(db.Integer, primary_key=True)
    termo         = db.Column(db.String(300), nullable=False, index=True)
    n_resultados  = db.Column(db.Integer, nullable=False, default=0)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow, index=True)
