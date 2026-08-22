from datetime import datetime
from app import db


# Tabela de associação da relação N:N entre posts e tags.
comunidade_post_tags = db.Table(
    "comunidade_post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("comunidade_posts.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("comunidade_tags.id"), primary_key=True),
)


class ComunidadeTag(db.Model):
    """Tag livre associada a publicações da Comunidade — folksonomia: criada
    pelos próprios utilizadores ao escrever (sem curadoria de admin), reaproveitada
    quando o mesmo slug já existe."""

    __tablename__ = "comunidade_tags"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(40), nullable=False)  # como foi escrita da 1ª vez (com acentos/maiúsculas)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ComunidadeTag {self.slug}>"


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
    # Prazo do destaque — None só é válido enquanto fixado=False; ao fixar,
    # a rota admin.fixar_post_comunidade define sempre uma data (ou permanente,
    # que também fica None mas é escolha explícita do moderador). Ver
    # esta_fixado_ativo, que é a fonte de verdade para mostrar o destaque.
    fixado_ate = db.Column(db.DateTime, nullable=True)

    respostas_count = db.Column(db.Integer, default=0, nullable=False)
    votos_score = db.Column(db.Integer, default=0, nullable=False, index=True)

    # Publicações ficam públicas de imediato (sem fila de aprovação) — estes campos
    # dão à moderação uma forma de "dar visto" a posts recentes proativamente,
    # sem depender só de denúncias de outros utilizadores.
    revisto = db.Column(db.Boolean, default=False, nullable=False, index=True)
    revisto_por_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    revisto_em = db.Column(db.DateTime, nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    autor = db.relationship("User", foreign_keys=[autor_id])
    revisto_por = db.relationship("User", foreign_keys=[revisto_por_id])
    respostas = db.relationship(
        "ComunidadeResposta", back_populates="post", lazy="dynamic",
        cascade="all, delete-orphan", order_by="ComunidadeResposta.criado_em",
    )
    imagens = db.relationship(
        "ComunidadePostImagem", back_populates="post", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    tags = db.relationship(
        "ComunidadeTag", secondary=comunidade_post_tags,
        backref=db.backref("posts", lazy="dynamic"),
    )

    @property
    def tipo_label(self) -> str:
        return dict(self.TIPOS).get(self.tipo, self.tipo)

    @property
    def esta_fixado_ativo(self) -> bool:
        """Fonte de verdade para mostrar o destaque "Fixado": só True se
        `fixado` estiver ligado E ainda dentro do prazo (ou sem prazo = permanente)."""
        if not self.fixado:
            return False
        return self.fixado_ate is None or self.fixado_ate > datetime.utcnow()

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
    """Resposta a um post da Comunidade. Suporta um único nível de threading:
    uma resposta pode ser direta ao post (parent_id=None) ou uma réplica a
    outra resposta (parent_id definido) — réplicas a réplicas não são permitidas,
    para manter a UI simples (mostram-se sempre indentadas sob o comentário-pai)."""

    __tablename__ = "comunidade_respostas"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("comunidade_posts.id"), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("comunidade_respostas.id"), nullable=True, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    corpo = db.Column(db.Text, nullable=False)
    votos_score = db.Column(db.Integer, default=0, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    post = db.relationship("ComunidadePost", back_populates="respostas")
    autor = db.relationship("User", foreign_keys=[autor_id])
    parent = db.relationship("ComunidadeResposta", remote_side=[id], backref=db.backref(
        "replicas", lazy="dynamic", order_by="ComunidadeResposta.criado_em",
        cascade="all, delete-orphan", single_parent=True,
    ))

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
