from datetime import datetime
from pathlib import Path
from app import db


class Categoria(db.Model):
    """Tipo de material (Prova, Resumo, Exercícios, etc.)."""

    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    icone = db.Column(db.String(50), default="📄")
    descricao = db.Column(db.String(200))

    materiais = db.relationship("Material", back_populates="categoria", lazy="dynamic")

    def __repr__(self):
        return f"<Categoria {self.nome}>"


class Material(db.Model):
    """Material académico submetido por um utilizador."""

    __tablename__ = "materiais"

    # Identificação
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)

    # Classificação académica
    instituicao = db.Column(db.String(200), nullable=False, index=True)
    curso = db.Column(db.String(200), index=True)
    disciplina = db.Column(db.String(200), nullable=False, index=True)
    ano_letivo = db.Column(db.String(10))        # ex: "2023/2024"
    ano_escolar = db.Column(db.String(20))        # ex: "3º Ano", "12ª Classe"
    semestre = db.Column(db.String(10))           # ex: "1", "2"

    # Ficheiro
    ficheiro_nome = db.Column(db.String(300), nullable=False)
    ficheiro_path = db.Column(db.String(500), nullable=False)
    ficheiro_tipo = db.Column(db.String(10))      # pdf, png, jpg, docx
    ficheiro_tamanho = db.Column(db.Integer)      # bytes

    # Estado de moderação
    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_REJEITADO = "rejeitado"

    status = db.Column(
        db.String(20),
        default=STATUS_PENDENTE,
        nullable=False,
        index=True
    )
    motivo_rejeicao = db.Column(db.Text)
    moderado_por_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Estatísticas
    visualizacoes = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)
    nota_media = db.Column(db.Float, default=0.0)

    # Agrupamento de uploads múltiplos (mesmo UUID = mesmo conjunto de fotos)
    grupo_upload = db.Column(db.String(36), index=True)

    # Chaves estrangeiras
    autor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"))

    # Timestamps
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relações
    autor = db.relationship("User", back_populates="materiais", foreign_keys=[autor_id])
    categoria = db.relationship("Categoria", back_populates="materiais")
    avaliacoes = db.relationship("Avaliacao", back_populates="material", lazy="dynamic", cascade="all, delete-orphan")
    favoritos = db.relationship("Favorito", backref="material", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def esta_aprovado(self) -> bool:
        return self.status == self.STATUS_APROVADO

    @property
    def titulo_base(self) -> str:
        """Para grupos, remove o sufixo '— Pág. X de N'."""
        if self.grupo_upload and " — Pág. " in self.titulo:
            return self.titulo.rsplit(" — Pág. ", 1)[0]
        return self.titulo

    @property
    def e_imagem(self) -> bool:
        return self.ficheiro_tipo in {"png", "jpg", "jpeg", "gif", "webp"}

    @property
    def tem_preview(self) -> bool:
        return self.ficheiro_tipo in {"png", "jpg", "jpeg", "gif", "webp", "pdf"}

    @property
    def thumbnail_path(self):
        """Caminho relativo para usar em url_for('static', filename=...)."""
        if not self.e_imagem:
            return None
        p = Path(self.ficheiro_path)
        return f"uploads/materiais/thumbs/{p.name}"

    def incrementar_visualizacoes(self):
        self.visualizacoes += 1

    def incrementar_downloads(self):
        self.downloads += 1

    def recalcular_nota(self):
        total = self.avaliacoes.count()
        if total == 0:
            self.nota_media = 0.0
            return
        soma = sum(a.nota for a in self.avaliacoes)
        self.nota_media = round(soma / total, 2)

    def __repr__(self):
        return f"<Material '{self.titulo}' [{self.status}]>"


class Favorito(db.Model):
    """Material guardado/favorito por um utilizador."""

    __tablename__ = "favoritos"

    id = db.Column(db.Integer, primary_key=True)
    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("materiais.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("utilizador_id", "material_id", name="uq_favorito_user_material"),
    )


class Avaliacao(db.Model):
    """Avaliação de um material por um utilizador (1-5 estrelas)."""

    __tablename__ = "avaliacoes"

    id = db.Column(db.Integer, primary_key=True)
    nota = db.Column(db.Integer, nullable=False)          # 1 a 5
    comentario = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    utilizador_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey("materiais.id"), nullable=False)

    utilizador = db.relationship("User", back_populates="avaliacoes")
    material = db.relationship("Material", back_populates="avaliacoes")

    __table_args__ = (
        db.UniqueConstraint("utilizador_id", "material_id", name="uq_avaliacao_user_material"),
    )

    def __repr__(self):
        return f"<Avaliacao {self.nota}★ por User#{self.utilizador_id}>"
