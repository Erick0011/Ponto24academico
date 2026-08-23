import uuid
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
    is_admin      = db.Column(db.Boolean, default=False)
    is_moderador  = db.Column(db.Boolean, default=False)
    is_active     = db.Column(db.Boolean, default=True)
    email_verificado = db.Column(db.Boolean, default=False)
    aceita_marketing = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_login = db.Column(db.DateTime)

    # Eliminação de conta (autoserviço, Definições > Eliminar conta) — distinto
    # de is_active (que é a suspensão feita por um admin): quando preenchido,
    # os dados pessoais já foram anonimizados e o login fica bloqueado, mas a
    # linha do utilizador mantém-se para não quebrar o autor_id de materiais,
    # avaliações e logs de atividade já publicados.
    conta_eliminada_em = db.Column(db.DateTime, nullable=True)

    # Relações
    materiais      = db.relationship("Material",      back_populates="autor",     foreign_keys="Material.autor_id",        lazy="dynamic")
    avaliacoes     = db.relationship("Avaliacao",     back_populates="utilizador", lazy="dynamic")
    favoritos      = db.relationship("Favorito",      backref="utilizador",        lazy="dynamic", foreign_keys="Favorito.utilizador_id")
    notificacoes   = db.relationship("Notificacao",   backref="utilizador",        lazy="dynamic", foreign_keys="Notificacao.utilizador_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def esta_eliminada(self) -> bool:
        return self.conta_eliminada_em is not None

    def anonimizar(self):
        """Eliminação de conta a pedido do próprio (Definições > Eliminar
        conta) — direito de apagamento da política de privacidade, §5/§6.
        Mantém a linha (e por isso os materiais e avaliações já
        publicados continuam íntegros, agora atribuídos a
        "Utilizador eliminado"), mas remove todos os dados pessoais e
        bloqueia logins futuros. Favoritos e notificações — só relevantes
        para o próprio — são apagados à parte pelo chamador."""
        self.nome = "Utilizador eliminado"
        self.email = f"eliminado-{self.id}@removido.ponto24.pt"
        self.password_hash = generate_password_hash(uuid.uuid4().hex)
        self.instituicao = None
        self.curso = None
        self.bio = None
        self.avatar_url = None
        self.aceita_marketing = False
        self.conta_eliminada_em = datetime.utcnow()

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
