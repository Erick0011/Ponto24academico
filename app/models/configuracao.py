from app import db


class Configuracao(db.Model):
    """Configurações da plataforma em formato chave-valor."""

    __tablename__ = "configuracoes"

    chave = db.Column(db.String(80), primary_key=True)
    valor = db.Column(db.Text, default="")

    @staticmethod
    def get(chave, default=""):
        c = Configuracao.query.get(chave)
        return c.valor if c else default

    @staticmethod
    def set(chave, valor):
        c = Configuracao.query.get(chave)
        if c:
            c.valor = str(valor)
        else:
            db.session.add(Configuracao(chave=chave, valor=str(valor)))

    @staticmethod
    def get_all_dict():
        return {c.chave: c.valor for c in Configuracao.query.all()}

    def __repr__(self):
        return f"<Config {self.chave}={self.valor!r}>"
