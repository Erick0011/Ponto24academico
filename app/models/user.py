from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    """Utilizador da plataforma."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Perfil
    instituicao = db.Column(db.String(200))
    curso = db.Column(db.String(200))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(300))

    # Créditos e gamificação
    creditos = db.Column(db.Integer, default=10, nullable=False)
    total_uploads = db.Column(db.Integer, default=0)
    total_downloads = db.Column(db.Integer, default=0)

    # Controlo
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    email_verificado = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_login = db.Column(db.DateTime)

    # Relações
    materiais = db.relationship("Material", back_populates="autor", foreign_keys="Material.autor_id", lazy="dynamic")
    avaliacoes = db.relationship("Avaliacao", back_populates="utilizador", lazy="dynamic")
    favoritos = db.relationship("Favorito", backref="utilizador", lazy="dynamic", foreign_keys="Favorito.utilizador_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def tem_creditos(self, quantidade: int = 1) -> bool:
        return self.creditos >= quantidade

    def gastar_creditos(self, quantidade: int):
        if not self.tem_creditos(quantidade):
            raise ValueError("Créditos insuficientes.")
        self.creditos -= quantidade

    def ganhar_creditos(self, quantidade: int):
        self.creditos += quantidade

    @property
    def nivel(self):
        c = self.creditos
        if c >= 1000:
            return {"nome": "Expert", "icone": "bi-trophy-fill", "cor_icone": "text-danger", "bg": "bg-danger", "proximo": None, "proximo_em": 1000, "pct": 100}
        elif c >= 500:
            return {"nome": "Colaborador Ouro", "icone": "bi-award-fill", "cor_icone": "text-warning", "bg": "bg-warning", "proximo": "Expert", "proximo_em": 1000, "pct": int((c - 500) / 500 * 100)}
        elif c >= 200:
            return {"nome": "Colaborador Prata", "icone": "bi-award-fill", "cor_icone": "text-secondary", "bg": "bg-secondary", "proximo": "Colaborador Ouro", "proximo_em": 500, "pct": int((c - 200) / 300 * 100)}
        elif c >= 50:
            return {"nome": "Colaborador Bronze", "icone": "bi-award", "cor_icone": "text-warning", "bg": "bg-warning", "proximo": "Colaborador Prata", "proximo_em": 200, "pct": int((c - 50) / 150 * 100)}
        else:
            return {"nome": "Novato", "icone": "bi-person-fill", "cor_icone": "text-muted", "bg": "bg-secondary", "proximo": "Colaborador Bronze", "proximo_em": 50, "pct": int(c / 50 * 100) if c > 0 else 0}

    def __repr__(self):
        return f"<User {self.email}>"
