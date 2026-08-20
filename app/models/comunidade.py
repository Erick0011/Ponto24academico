from datetime import datetime
from app import db


class ComunidadePost(db.Model):
    """Publicação da secção Comunidade — pergunta, discussão ou aviso."""

    __tablename__ = "comunidade_posts"

    TIPO_DUVIDA = "duvida"
    TIPO_DISCUSSAO = "discussao"
    TIPO_AVISO = "aviso"
    TIPOS = [
        (TIPO_DUVIDA, "Dúvida"),
        (TIPO_DISCUSSAO, "Discussão"),
        (TIPO_AVISO, "Aviso"),
    ]

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    corpo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default=TIPO_DISCUSSAO)

    autor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    fixado = db.Column(db.Boolean, default=False, nullable=False)

    respostas_count = db.Column(db.Integer, default=0, nullable=False)
    votos_score = db.Column(db.Integer, default=0, nullable=False, index=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    autor = db.relationship("User", foreign_keys=[autor_id])
    respostas = db.relationship(
        "ComunidadeResposta", back_populates="post", lazy="dynamic",
        cascade="all, delete-orphan", order_by="ComunidadeResposta.criado_em",
    )
    imagens = db.relationship(
        "ComunidadePostImagem", back_populates="post", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def tipo_label(self) -> str:
        return dict(self.TIPOS).get(self.tipo, self.tipo)

    def __repr__(self):
        return f"<ComunidadePost {self.id} '{self.titulo}'>"


class ComunidadePostImagem(db.Model):
    """Uma foto anexada a um post da Comunidade."""

    __tablename__ = "comunidade_post_imagens"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("comunidade_posts.id"), nullable=False, index=True)
    path_relativo = db.Column(db.String(500), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("ComunidadePost", back_populates="imagens")


class ComunidadeResposta(db.Model):
    """Resposta a um post da Comunidade — sem threading (nível único)."""

    __tablename__ = "comunidade_respostas"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("comunidade_posts.id"), nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    corpo = db.Column(db.Text, nullable=False)
    votos_score = db.Column(db.Integer, default=0, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    post = db.relationship("ComunidadePost", back_populates="respostas")
    autor = db.relationship("User", foreign_keys=[autor_id])

    def __repr__(self):
        return f"<ComunidadeResposta {self.id} post={self.post_id}>"


class ComunidadeVoto(db.Model):
    """Voto (+1/-1) de um utilizador num post ou resposta.
    alvo_tipo/alvo_id seguem o padrão polimórfico-por-convenção já usado em
    AtividadeLog/RelatorioMaterial — evita duas tabelas de voto quase iguais."""

    __tablename__ = "comunidade_votos"
    __table_args__ = (
        db.UniqueConstraint("utilizador_id", "alvo_tipo", "alvo_id", name="uq_voto_user_alvo"),
    )

    ALVO_POST = "post"
    ALVO_RESPOSTA = "resposta"

    id = db.Column(db.Integer, primary_key=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    alvo_tipo = db.Column(db.String(20), nullable=False)
    alvo_id = db.Column(db.Integer, nullable=False, index=True)
    valor = db.Column(db.Integer, nullable=False)  # +1 ou -1
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    utilizador = db.relationship("User")


class ComunidadeRelatorio(db.Model):
    """Denúncia de um post ou resposta da Comunidade — mesmo fluxo de
    RelatorioMaterial (status pendente/resolvido/ignorado)."""

    __tablename__ = "comunidade_relatorios"

    MOTIVOS = [
        ("spam", "Spam ou publicidade não autorizada"),
        ("ofensivo", "Conteúdo ofensivo ou discurso de ódio"),
        ("inapropriado", "Conteúdo inapropriado"),
        ("assedio", "Assédio a outro utilizador"),
        ("outro", "Outro motivo"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_RESOLVIDO = "resolvido"
    STATUS_IGNORADO = "ignorado"

    id = db.Column(db.Integer, primary_key=True)
    alvo_tipo = db.Column(db.String(20), nullable=False)  # "post" | "resposta"
    alvo_id = db.Column(db.Integer, nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    motivo = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20), default=STATUS_PENDENTE, nullable=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    autor = db.relationship("User")
