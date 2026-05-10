"""
Comandos CLI para gestão da aplicação.
Uso: flask --app run.py <comando>
"""
import click
from flask import current_app
from app import db, create_app
from app.models.user import User
from app.models.material import Categoria

app = create_app()


@app.cli.command("seed-db")
def seed_db():
    """Popula a base de dados com dados iniciais (categorias, etc.)."""
    categorias_base = [
        ("Prova", "bi-file-text", "Exames e testes de anos anteriores"),
        ("Resumo", "bi-book", "Resumos e sínteses de matérias"),
        ("Exercícios", "bi-pencil-square", "Listas e fichas de exercícios"),
        ("Apontamentos", "bi-journal-text", "Notas de aulas e apontamentos"),
        ("Gabarito", "bi-check-square", "Soluções e respostas de exercícios"),
        ("Slides", "bi-display", "Apresentações e slides de aulas"),
        ("Outro", "bi-file-earmark", "Outros tipos de materiais"),
    ]

    for nome, icone, descricao in categorias_base:
        if not Categoria.query.filter_by(nome=nome).first():
            db.session.add(Categoria(nome=nome, icone=icone, descricao=descricao))
            click.echo(f"  ✓ Categoria criada: {nome}")

    db.session.commit()
    click.echo("✅ Base de dados populada com sucesso!")


@app.cli.command("criar-admin")
@click.argument("email")
@click.argument("password")
def criar_admin(email, password):
    """Cria ou promove um utilizador a administrador."""
    user = User.query.filter_by(email=email).first()

    if user:
        user.is_admin = True
        click.echo(f"✓ Utilizador '{email}' promovido a admin.")
    else:
        user = User(
            nome="Administrador",
            email=email,
            is_admin=True,
            creditos=999,
        )
        user.set_password(password)
        db.session.add(user)
        click.echo(f"✓ Admin criado: {email}")

    db.session.commit()


if __name__ == "__main__":
    app.run()
