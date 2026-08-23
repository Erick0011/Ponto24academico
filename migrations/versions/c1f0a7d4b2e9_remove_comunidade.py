"""remove a funcionalidade Comunidade (tabelas e colunas de moderação no User)

Revision ID: c1f0a7d4b2e9
Revises: e390e8b34e5b
Create Date: 2026-08-22 23:10:00.000000

Esta migração é destrutiva e não tem downgrade: apaga todas as publicações,
respostas, votos, reações, denúncias, notificações e o log de auditoria da
Comunidade, bem como os ficheiros das imagens carregadas. Para voltar atrás é
preciso restaurar um backup da base de dados anterior a este upgrade.
"""
import os

from alembic import op
import sqlalchemy as sa
from flask import current_app


# revision identifiers, used by Alembic.
revision = 'c1f0a7d4b2e9'
down_revision = 'e390e8b34e5b'
branch_labels = None
depends_on = None


# Ordem de drop = filhos antes dos pais, para nenhuma FK ficar pendurada em
# Postgres (em SQLite a ordem é indiferente, mas manter uma só ordem evita
# divergências entre ambientes).
TABELAS = [
    'comunidade_audit_log',
    'comunidade_links',
    'comunidade_reacoes',
    'comunidade_subscricoes',
    'comunidade_votos',
    'comunidade_relatorios',
    'comunidade_resposta_imagens',
    'comunidade_post_imagens',
    'comunidade_post_tags',
    'comunidade_respostas',
    'comunidade_posts',
    'comunidade_categorias',
    'comunidade_tags',
]


def _limpar_imagens(conn):
    """Apaga os ficheiros das imagens antes de as linhas desaparecerem.

    As imagens da Comunidade nunca foram removidas por cascade: o código antigo
    chamava `apagar_ficheiro(img.path_relativo)` explicitamente antes de apagar
    o post. Se largarmos as tabelas sem isto, os ficheiros ficam no disco/R2 para
    sempre e deixa de existir qualquer forma de os enumerar. Por isso o manifesto
    é gravado *primeiro* — mesmo que a remoção falhe, a lista fica recuperável.
    """
    paths = []
    for tabela in ("comunidade_post_imagens", "comunidade_resposta_imagens"):
        linhas = conn.execute(sa.text(f"SELECT path_relativo FROM {tabela}")).fetchall()
        paths.extend(linha[0] for linha in linhas if linha[0])

    if not paths:
        return

    manifesto = os.path.join(current_app.instance_path, "comunidade_imagens_removidas.txt")
    os.makedirs(current_app.instance_path, exist_ok=True)
    with open(manifesto, "w", encoding="utf-8") as f:
        f.write("\n".join(paths) + "\n")
    print(f"[c1f0a7d4b2e9] {len(paths)} imagens listadas em {manifesto}")

    from app.services.upload_service import apagar_ficheiro
    falhas = 0
    for path in paths:
        try:
            apagar_ficheiro(path)
        except Exception as e:  # ficheiro já ausente, R2 indisponível, etc.
            falhas += 1
            print(f"[c1f0a7d4b2e9] falhou apagar {path}: {e}")
    if falhas:
        print(f"[c1f0a7d4b2e9] {falhas} ficheiros por apagar — ver manifesto acima")


def upgrade():
    conn = op.get_bind()

    _limpar_imagens(conn)

    # As notificações de resposta/melhor resposta apontam para /comunidade/<id>,
    # que deixou de existir: sem isto o utilizador clica e apanha um 404.
    conn.execute(sa.text("DELETE FROM notificacoes WHERE tipo LIKE 'comunidade%'"))

    # comunidade_posts.melhor_resposta_id aponta para comunidade_respostas e
    # comunidade_respostas.post_id aponta de volta para comunidade_posts: a
    # dependência é circular, por isso esta FK sai primeiro.
    with op.batch_alter_table('comunidade_posts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_comunidade_posts_melhor_resposta_id', type_='foreignkey')
        batch_op.drop_column('melhor_resposta_id')

    for tabela in TABELAS:
        op.drop_table(tabela)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('comunidade_suspensao_motivo')
        batch_op.drop_column('comunidade_suspenso_ate')
        batch_op.drop_column('comunidade_banido')


def downgrade():
    raise NotImplementedError(
        "Remoção da Comunidade é irreversível: os dados foram apagados. "
        "Para reverter, restaura um backup anterior ao upgrade c1f0a7d4b2e9."
    )
