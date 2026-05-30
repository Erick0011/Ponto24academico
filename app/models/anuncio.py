from datetime import date
from app import db


class Anuncio(db.Model):
    __tablename__ = "anuncios"

    id           = db.Column(db.Integer, primary_key=True)
    anunciante   = db.Column(db.String(120), nullable=False)
    contacto     = db.Column(db.String(120), default="")
    banner_url   = db.Column(db.String(500), nullable=False)   # URL da imagem
    link_destino = db.Column(db.String(500), default="")       # URL de clique
    percentagem  = db.Column(db.Float, nullable=False)         # 10 / 25 / 50
    data_inicio  = db.Column(db.Date, nullable=False)
    data_fim     = db.Column(db.Date, nullable=False)
    ativo        = db.Column(db.Boolean, default=True)
    criado_em    = db.Column(db.DateTime, default=db.func.now())

    @property
    def dias_restantes(self):
        delta = (self.data_fim - date.today()).days
        return max(0, delta)

    @property
    def esta_ativo(self):
        hoje = date.today()
        return self.ativo and self.data_inicio <= hoje <= self.data_fim

    @staticmethod
    def percentagem_disponivel():
        hoje = date.today()
        activos = Anuncio.query.filter(
            Anuncio.ativo == True,
            Anuncio.data_inicio <= hoje,
            Anuncio.data_fim >= hoje,
        ).all()
        return max(0, 100 - sum(a.percentagem for a in activos))

    @staticmethod
    def selecionar():
        import random
        hoje = date.today()
        banners = Anuncio.query.filter(
            Anuncio.ativo == True,
            Anuncio.data_inicio <= hoje,
            Anuncio.data_fim >= hoje,
        ).all()
        if not banners:
            return None
        total = sum(b.percentagem for b in banners)
        r = random.uniform(0, 100)
        if r > total:
            return None
        acumulado = 0
        for b in banners:
            acumulado += b.percentagem
            if r <= acumulado:
                return b
        return banners[-1]
