from datetime import datetime
from app import db  # ou from your_project import db
import json


class Candidatura(db.Model):
    __tablename__ = "candidaturas"

    id = db.Column(db.Integer, primary_key=True)

    # 1. Dados pessoais
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, index=True)
    telefone = db.Column(db.String(30), nullable=True)
    universidade = db.Column(db.String(100), nullable=True)
    curso = db.Column(db.String(100), nullable=True)
    ano = db.Column(db.String(50), nullable=True)  # 1º, 2º, Finalista, etc.

    # 2. Contribuições (guardadas como JSON string)
    contribuicoes = db.Column(db.Text, nullable=True, default="[]")

    # 3. Motivação
    motivacao = db.Column(db.Text, nullable=True)
    impacto = db.Column(db.Text, nullable=True)

    # 4. Experiência
    experiencia = db.Column(db.Text, nullable=True)

    # 5. Liderança
    lideranca = db.Column(
        db.String(20), nullable=True, default="nao"
    )  # nao, sim, futuro
    area = db.Column(db.String(50), nullable=True)
    lideranca_motivo = db.Column(db.Text, nullable=True)

    # Meta
    status = db.Column(
        db.String(30), default="pendente"
    )  # pendente, aprovado, rejeitado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Candidatura {self.nome} ({self.email})>"

    def get_contribuicoes_list(self):
        """Retorna a lista de contribuições em Python."""
        try:
            return json.loads(self.contribuicoes) if self.contribuicoes else []
        except json.JSONDecodeError:
            return []

    def set_contribuicoes_list(self, lista):
        """Recebe uma lista Python e guarda como JSON string."""
        self.contribuicoes = json.dumps(lista, ensure_ascii=False)
