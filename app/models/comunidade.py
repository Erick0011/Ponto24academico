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


class ComunidadeCategoria(db.Model):
    """Categoria administrável da Comunidade (Anúncios, Dúvidas, Pedidos de
    Material, Partilhas, Geral, ...) — substitui gradualmente o antigo enum
    fixo `ComunidadePost.tipo` (mantido como campo derivado, só para não
    partir código/links antigos que ainda filtram por `tipo`)."""

    __tablename__ = "comunidade_categorias"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(200))
    icone = db.Column(db.String(50), default="bi-chat-dots", nullable=False)
    ordem = db.Column(db.Integer, default=0, nullable=False)
    # Quem pode publicar nesta categoria: True = só admin/moderador (ex:
    # Anúncios oficiais); False = qualquer membro.
    apenas_admin = db.Column(db.Boolean, default=False, nullable=False)
    # Soft-hide: uma categoria com posts nunca pode ser apagada (partiria o
    # FK), só desativada — deixa de aparecer para criar posts novos, mas os
    # posts já existentes continuam a mostrá-la normalmente.
    ativa = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship("ComunidadePost", back_populates="categoria", lazy="dynamic")

    def __repr__(self):
        return f"<ComunidadeCategoria {self.slug}>"


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

    ESTADO_ABERTO = "aberto"
    ESTADO_RESOLVIDO = "resolvido"
    ESTADO_FECHADO = "fechado"
    ESTADOS = [
        (ESTADO_ABERTO, "Aberto"),
        (ESTADO_RESOLVIDO, "Resolvido"),
        (ESTADO_FECHADO, "Fechado"),
    ]

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    corpo = db.Column(db.Text, nullable=False)
    # Legado — mantido por compatibilidade (filtros/links antigos, badge de
    # "Aviso oficial"). Derivado automaticamente da categoria ao publicar;
    # para posts sem categoria (anteriores a esta migração) fica como estava.
    tipo = db.Column(db.String(20), nullable=False, default=TIPO_DISCUSSAO)
    categoria_id = db.Column(db.Integer, db.ForeignKey("comunidade_categorias.id"), nullable=True, index=True)
    estado = db.Column(db.String(20), nullable=False, default=ESTADO_ABERTO, index=True)
    editado = db.Column(db.Boolean, default=False, nullable=False)

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
        foreign_keys="ComunidadeResposta.post_id",
    )
    imagens = db.relationship(
        "ComunidadePostImagem", back_populates="post", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    tags = db.relationship(
        "ComunidadeTag", secondary=comunidade_post_tags,
        backref=db.backref("posts", lazy="dynamic"),
    )
    categoria = db.relationship("ComunidadeCategoria", back_populates="posts")

    # Melhor resposta — marcada pelo autor do tópico ou por um moderador.
    # FK "solto" (sem back_populates) porque ComunidadeResposta já aponta
    # para ComunidadePost via post_id; ligar os dois lados criaria um ciclo
    # de relationship sem necessidade — aqui só precisamos do id.
    melhor_resposta_id = db.Column(db.Integer, db.ForeignKey("comunidade_respostas.id"), nullable=True)
    melhor_resposta = db.relationship("ComunidadeResposta", foreign_keys=[melhor_resposta_id])

    @property
    def tipo_label(self) -> str:
        return dict(self.TIPOS).get(self.tipo, self.tipo)

    @property
    def estado_label(self) -> str:
        return dict(self.ESTADOS).get(self.estado, self.estado)

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
    editado = db.Column(db.Boolean, default=False, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    post = db.relationship("ComunidadePost", back_populates="respostas", foreign_keys=[post_id])
    autor = db.relationship("User", foreign_keys=[autor_id])
    parent = db.relationship("ComunidadeResposta", remote_side=[id], backref=db.backref(
        "replicas", lazy="dynamic", order_by="ComunidadeResposta.criado_em",
        cascade="all, delete-orphan", single_parent=True,
    ))
    imagens = db.relationship(
        "ComunidadeRespostaImagem", back_populates="resposta", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def e_melhor_resposta(self) -> bool:
        return self.post is not None and self.post.melhor_resposta_id == self.id

    def __repr__(self):
        return f"<ComunidadeResposta {self.id} post={self.post_id}>"


class ComunidadeRespostaImagem(db.Model):
    """Uma foto anexada a uma resposta/comentário da Comunidade — mesmo
    padrão de ComunidadePostImagem, para os comentários poderem discutir
    com imagens (ex: fotos de exercícios, prints de erros)."""

    __tablename__ = "comunidade_resposta_imagens"

    id = db.Column(db.Integer, primary_key=True)
    resposta_id = db.Column(db.Integer, db.ForeignKey("comunidade_respostas.id"), nullable=False, index=True)
    path_relativo = db.Column(db.String(500), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    resposta = db.relationship("ComunidadeResposta", back_populates="imagens")


class ComunidadeSubscricao(db.Model):
    """Subscrição de um utilizador a um tópico — recebe notificação de
    qualquer resposta nova, mesmo sem ser o autor nem ter respondido. O autor
    do tópico e quem responde ficam subscritos automaticamente (ver
    app/routes/comunidade.py: criar_post/criar_resposta)."""

    __tablename__ = "comunidade_subscricoes"
    __table_args__ = (
        db.UniqueConstraint("utilizador_id", "post_id", name="uq_subscricao_user_post"),
    )

    id = db.Column(db.Integer, primary_key=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey("comunidade_posts.id"), nullable=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    utilizador = db.relationship("User")
    post = db.relationship(
        "ComunidadePost",
        backref=db.backref("subscricoes", lazy="dynamic", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        return f"<ComunidadeSubscricao user={self.utilizador_id} post={self.post_id}>"


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


class ComunidadeReacao(db.Model):
    """Reação nomeada (Útil / Obrigado / Resolvido) — a par do voto (+1/-1),
    não em substituição: o voto mede qualidade geral, a reação diz uma coisa
    específica sobre o conteúdo. Mesmo padrão alvo_tipo/alvo_id de
    ComunidadeVoto. Um utilizador pode marcar mais do que um tipo no mesmo
    alvo (ex: "Útil" e "Obrigado" ao mesmo tempo), por isso o tipo entra na
    unique constraint."""

    __tablename__ = "comunidade_reacoes"
    __table_args__ = (
        db.UniqueConstraint("utilizador_id", "alvo_tipo", "alvo_id", "tipo", name="uq_reacao_user_alvo_tipo"),
    )

    ALVO_POST = "post"
    ALVO_RESPOSTA = "resposta"

    UTIL = "util"
    OBRIGADO = "obrigado"
    RESOLVIDO = "resolvido"
    TIPOS = [
        (UTIL, "Útil"),
        (OBRIGADO, "Obrigado"),
        (RESOLVIDO, "Resolvido"),
    ]
    ICONES = {UTIL: "bi-hand-thumbs-up", OBRIGADO: "bi-heart", RESOLVIDO: "bi-check-circle"}

    id = db.Column(db.Integer, primary_key=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    alvo_tipo = db.Column(db.String(20), nullable=False)
    alvo_id = db.Column(db.Integer, nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False)
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


class ComunidadeLink(db.Model):
    """Ligação interna entre conteúdos — de um tópico ou resposta para um
    material, outro tópico, ou outra resposta. Model único e polimórfico:
    as três formas de ligar (sintaxe #123/@material:456 no texto, colar um
    URL interno, ou um futuro botão "Anexar") escrevem todas nesta mesma
    tabela — as ligações inversas ("Discutido em N tópicos", "Referenciado
    por") são uma simples query, nunca duplicam dados.

    Ver app/services/comunidade_links_service.py para a deteção/renderização."""

    __tablename__ = "comunidade_links"
    __table_args__ = (
        db.UniqueConstraint("source_tipo", "source_id", "target_tipo", "target_id", name="uq_link_source_target"),
        db.Index("ix_comunidade_links_source", "source_tipo", "source_id"),
        db.Index("ix_comunidade_links_target", "target_tipo", "target_id"),
    )

    SOURCE_TOPICO = "topico"
    SOURCE_RESPOSTA = "resposta"
    TARGET_MATERIAL = "material"
    TARGET_TOPICO = "topico"
    TARGET_RESPOSTA = "resposta"

    id = db.Column(db.Integer, primary_key=True)
    source_tipo = db.Column(db.String(20), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    target_tipo = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    criado_por_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    criado_por = db.relationship("User")

    def __repr__(self):
        return f"<ComunidadeLink {self.source_tipo}:{self.source_id} -> {self.target_tipo}:{self.target_id}>"


class ComunidadeAuditLog(db.Model):
    """Log de auditoria da Comunidade — imutável por convenção: nenhuma rota
    da aplicação faz UPDATE nem DELETE sobre esta tabela, só INSERT (ver
    app/services/comunidade_auditoria_service.py). Complementa o AtividadeLog
    genérico (esse alimenta o KPI): este guarda o antes/depois de cada
    mutação, para efeitos de compliance. Consulta em Admin > Auditoria."""

    __tablename__ = "comunidade_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    entity_type = db.Column(db.String(30), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    payload_before = db.Column(db.JSON, nullable=True)
    payload_after = db.Column(db.JSON, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    actor = db.relationship("User")

    def __repr__(self):
        return f"<ComunidadeAuditLog {self.action} {self.entity_type}:{self.entity_id}>"
