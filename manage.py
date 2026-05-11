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


@app.cli.command("testar-email")
@click.argument("destinatario")
def testar_email(destinatario):
    """Envia os 3 tipos de email de teste para o endereço indicado."""
    from app.services.mail_service import enviar_email

    class MockUser:
        nome = "Erick Baptista"
        email = destinatario
        creditos = 10

    class MockCategoria:
        nome = "Prova"

    class MockMaterial:
        titulo_base = "Prova de Cálculo I — 1ª Frequência 2024/2025"
        disciplina = "Cálculo I"
        ano_letivo = "2024/2025"
        semestre = "1"
        categoria = MockCategoria()
        autor = MockUser()

    user = MockUser()
    material = MockMaterial()

    click.echo(f"A enviar emails para {destinatario}...")

    ok1 = enviar_email(
        destinatario,
        "Bem-vindo(a) ao Ponto 24 Académico!",
        "email/boas_vindas.html",
        {"user": user},
    )
    click.echo(f"  {'OK' if ok1 else 'FALHOU'} — Boas-vindas")

    ok2 = enviar_email(
        destinatario,
        f"Material aprovado — {material.titulo_base}",
        "email/material_aprovado.html",
        {"material": material, "user": user},
    )
    click.echo(f"  {'OK' if ok2 else 'FALHOU'} — Material aprovado")

    ok3 = enviar_email(
        destinatario,
        f"Material rejeitado — {material.titulo_base}",
        "email/material_rejeitado.html",
        {"material": material, "user": user, "motivo": "Ficheiro ilegível ou de baixa qualidade"},
    )
    click.echo(f"  {'OK' if ok3 else 'FALHOU'} — Material rejeitado")

    if ok1 and ok2 and ok3:
        click.echo("Todos os emails enviados com sucesso!")
    else:
        click.echo("Alguns emails falharam. Verifica os logs acima.")


if __name__ == "__main__":
    app.run()
