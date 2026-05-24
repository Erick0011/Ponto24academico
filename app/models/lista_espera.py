from datetime import datetime
from app import db


class ListaEspera(db.Model):
    """Pedidos de acesso antecipado à plataforma."""

    __tablename__ = "lista_espera"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120))
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    instituicao = db.Column(db.String(200))
    mensagem = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    STATUS_PENDENTE  = "pendente"
    STATUS_CONVIDADO = "convidado"
    STATUS_REGISTADO = "registado"

    status = db.Column(db.String(20), default="pendente", nullable=False, index=True)

    def __repr__(self):
        return f"<ListaEspera {self.email} [{self.status}]>"


class RelatorioMaterial(db.Model):
    """Reporte de material inadequado ou com problemas."""

    __tablename__ = "relatorios_materiais"

    MOTIVOS = [
        ("duplicado",    "Material duplicado"),
        ("errado",       "Conteúdo errado ou enganoso"),
        ("qualidade",    "Má qualidade / ilegível"),
        ("direitos",     "Violação de direitos de autor"),
        ("inapropriado", "Conteúdo inapropriado"),
        ("outro",        "Outro motivo"),
    ]

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materiais.id"), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    motivo = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    STATUS_PENDENTE  = "pendente"
    STATUS_RESOLVIDO = "resolvido"
    STATUS_IGNORADO  = "ignorado"

    status = db.Column(db.String(20), default="pendente", nullable=False, index=True)

    material = db.relationship("Material", backref=db.backref("relatorios", lazy="dynamic"))
    autor    = db.relationship("User")

    def __repr__(self):
        return f"<Relatorio Material#{self.material_id} [{self.motivo}]>"
