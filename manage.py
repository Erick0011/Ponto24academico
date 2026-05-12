"""
Comandos CLI para gestão da aplicação.
Uso: flask --app manage.py <comando>

Comandos disponíveis:
  seed-db                         Cria categorias base
  criar-admin <email> <password>  Cria ou promove admin
  testar-email <destinatario>     Envia emails de teste
  importar-lote <pasta> [opções]  Importa materiais em massa

Uso do importar-lote:
  Organiza os ficheiros assim:
    pasta/
      INSTITUICAO/
        DISCIPLINA/
          CATEGORIA/        (deve corresponder a uma categoria existente)
            ficheiro.pdf

  Exemplos:
    flask --app manage.py importar-lote ./importar
    flask --app manage.py importar-lote ./importar --ano-letivo "2024/2025" --auto-aprovar
    flask --app manage.py importar-lote ./importar --autor admin@ponto24.ao --dry-run

  Opções:
    --ano-letivo TEXT    Ano letivo aplicado a todos (ex: "2024/2025")
    --auto-aprovar      Aprova os materiais sem moderação
    --autor EMAIL       Email do utilizador autor (default: primeiro admin)
    --dry-run           Mostra o que seria importado sem fazer nada
"""
import os
import re
import uuid
import shutil
import unicodedata
import click
from datetime import datetime
from pathlib import Path
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



@app.cli.command("importar-lote")
@click.argument("pasta", type=click.Path(exists=True, file_okay=False))
@click.option("--ano-letivo",   default="",    help='Ano letivo ex: "2024/2025"')
@click.option("--auto-aprovar", is_flag=True,  help="Aprovar sem moderação")
@click.option("--autor",        "autor_email", default=None, help="Email do autor (default: primeiro admin)")
@click.option("--dry-run",      is_flag=True,  help="Simula sem importar nada")
def importar_lote(pasta, ano_letivo, auto_aprovar, autor_email, dry_run):
    """Importa materiais em massa a partir de uma pasta organizada.

    Estrutura esperada: pasta/INSTITUICAO/DISCIPLINA/CATEGORIA/ficheiro
    """
    from app.models.material import Material
    from app.services.upload_service import calcular_hash, _gerar_thumbnail

    EXTENSOES = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "docx"}

    # ── Autor ──────────────────────────────────────────────────────────────
    if autor_email:
        autor = User.query.filter_by(email=autor_email).first()
        if not autor:
            click.echo(f"ERRO: utilizador '{autor_email}' nao encontrado.", err=True)
            return
    else:
        autor = User.query.filter_by(is_admin=True).first()
        if not autor:
            click.echo("ERRO: nenhum admin encontrado. Corre 'criar-admin' primeiro.", err=True)
            return

    click.echo(f"Autor: {autor.nome} ({autor.email})")

    # ── Categorias (nome lowercase → objeto) ───────────────────────────────
    categorias_db = {c.nome.lower(): c for c in Categoria.query.all()}
    if not categorias_db:
        click.echo("ERRO: sem categorias na base de dados. Corre 'seed-db' primeiro.", err=True)
        return

    # ── Descobrir ficheiros ────────────────────────────────────────────────
    pasta_path = Path(pasta).resolve()
    ficheiros = []

    for inst_dir in sorted(pasta_path.iterdir()):
        if not inst_dir.is_dir():
            continue
        for disc_dir in sorted(inst_dir.iterdir()):
            if not disc_dir.is_dir():
                continue
            for cat_dir in sorted(disc_dir.iterdir()):
                if not cat_dir.is_dir():
                    continue
                for f in sorted(cat_dir.iterdir()):
                    if f.is_file() and f.suffix.lstrip(".").lower() in EXTENSOES:
                        ficheiros.append((f, inst_dir.name, disc_dir.name, cat_dir.name))

    total = len(ficheiros)
    click.echo(f"Ficheiros encontrados: {total}")

    if total == 0:
        click.echo("Nenhum ficheiro encontrado. Verifica a estrutura de pastas.")
        return

    if dry_run:
        click.echo("\n[DRY RUN] — nada sera importado\n")
        for f, inst, disc, cat in ficheiros:
            cat_obj = _resolver_categoria(cat, categorias_db)
            flag = "" if cat_obj else "  [CATEGORIA NAO ENCONTRADA]"
            click.echo(f"  {inst} / {disc} / {cat} / {f.name}{flag}")
        click.echo(f"\nTotal: {total} ficheiros")
        return

    # ── Importar ───────────────────────────────────────────────────────────
    upload_base  = current_app.config["UPLOAD_FOLDER"]
    agora        = datetime.now()
    status       = Material.STATUS_APROVADO if auto_aprovar else Material.STATUS_PENDENTE
    stats        = {"ok": 0, "duplicados": 0, "sem_cat": 0, "erros": 0}

    with click.progressbar(ficheiros, label="A importar", width=40) as bar:
        for ficheiro_path, instituicao, disciplina, cat_nome in bar:
            try:
                ext      = ficheiro_path.suffix.lstrip(".").lower()
                hash_val = calcular_hash(str(ficheiro_path))

                # Duplicado?
                if Material.query.filter_by(ficheiro_hash=hash_val).first():
                    stats["duplicados"] += 1
                    continue

                # Categoria
                cat_obj  = _resolver_categoria(cat_nome, categorias_db)
                if not cat_obj:
                    stats["sem_cat"] += 1

                # Pasta de destino: materiais/{cat_slug}/{YYYY}/{MM}/
                cat_slug    = _slugify(cat_nome)
                subfolder   = f"materiais/{cat_slug}/{agora.strftime('%Y')}/{agora.strftime('%m')}"
                destino_dir = os.path.join(upload_base, subfolder)
                os.makedirs(destino_dir, exist_ok=True)

                nome_guardado = f"{uuid.uuid4().hex}.{ext}"
                destino       = os.path.join(destino_dir, nome_guardado)
                shutil.copy2(str(ficheiro_path), destino)

                path_relativo = f"{subfolder}/{nome_guardado}"

                if ext in {"png", "jpg", "jpeg", "gif", "webp"}:
                    _gerar_thumbnail(destino, destino_dir, nome_guardado)

                material = Material(
                    titulo        = ficheiro_path.stem,
                    instituicao   = instituicao,
                    disciplina    = disciplina,
                    ano_letivo    = ano_letivo,
                    categoria_id  = cat_obj.id if cat_obj else None,
                    ficheiro_nome = ficheiro_path.name,
                    ficheiro_path = path_relativo,
                    ficheiro_tipo = ext,
                    ficheiro_tamanho = os.path.getsize(destino),
                    ficheiro_hash = hash_val,
                    autor_id      = autor.id,
                    status        = status,
                )
                db.session.add(material)
                stats["ok"] += 1

                # Commit em lotes de 100
                if stats["ok"] % 100 == 0:
                    db.session.commit()

            except Exception as e:
                stats["erros"] += 1
                click.echo(f"\n  ERRO {ficheiro_path.name}: {e}", err=True)

    db.session.commit()

    click.echo(f"\n{'─'*40}")
    click.echo(f"  Importados : {stats['ok']}")
    click.echo(f"  Duplicados : {stats['duplicados']} (ignorados)")
    click.echo(f"  Sem cat.   : {stats['sem_cat']} (importados sem categoria)")
    click.echo(f"  Erros      : {stats['erros']}")
    click.echo(f"{'─'*40}")
    if not auto_aprovar and stats["ok"] > 0:
        click.echo("  Os materiais estao pendentes de aprovacao.")
        click.echo("  Para aprovar tudo de uma vez, usa --auto-aprovar.")


def _resolver_categoria(nome, categorias_db):
    """Tenta encontrar a categoria pelo nome ou parcialmente."""
    nome_l = nome.lower()
    if nome_l in categorias_db:
        return categorias_db[nome_l]
    for k, v in categorias_db.items():
        if k in nome_l or nome_l in k:
            return v
    return None


def _slugify(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "_", s).strip("_") or "geral"


if __name__ == "__main__":
    app.run()
