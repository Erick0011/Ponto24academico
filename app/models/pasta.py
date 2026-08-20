from datetime import datetime
from app import db


class Pasta(db.Model):
    """Nó de uma hierarquia de pastas para organizar materiais
    (ex: Universidade/Curso/Semestre/Disciplina/Ano — profundidade e nomes livres).
    """

    __tablename__ = "pastas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("pastas.id"), nullable=True, index=True)

    # Caminho materializado: ids dos antepassados + próprio id, separados por "/", ex: "3/7/12".
    # Computado na criação (ver rota admin.criar_pasta) — nunca recalculado depois, pois esta
    # fase só suporta criar/eliminar pastas, não mover/renomear.
    caminho = db.Column(db.String(500), nullable=False, index=True)
    nivel = db.Column(db.Integer, nullable=False, default=0)  # profundidade, raiz = 0

    criado_por_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    parent = db.relationship(
        "Pasta", remote_side=[id],
        backref=db.backref("filhos", lazy="dynamic", order_by="Pasta.nome"),
    )
    criado_por = db.relationship("User", foreign_keys=[criado_por_id])
    materiais = db.relationship("Material", back_populates="pasta", lazy="dynamic")

    @property
    def caminho_display(self) -> str:
        """Breadcrumb legível, ex: 'ISAF > Informática > 3º Semestre'."""
        partes, no = [], self
        while no is not None:
            partes.append(no.nome)
            no = no.parent
        return " > ".join(reversed(partes))

    def ids_subquery(self):
        """Subquery de ids: o próprio nó + todos os descendentes, via o caminho materializado."""
        return db.session.query(Pasta.id).filter(
            db.or_(Pasta.id == self.id, Pasta.caminho.like(f"{self.caminho}/%"))
        )

    def __repr__(self):
        return f"<Pasta '{self.nome}' (id={self.id}, nivel={self.nivel})>"
