"""remove a funcionalidade Comunidade (tabelas e colunas de moderação no User)

Revision ID: c1f0a7d4b2e9
Revises: e390e8b34e5b
Create Date: 2026-08-22 23:10:00.000000

Esta migração é destrutiva e não tem downgrade: apaga todas as publicações,
respostas, votos, reações, denúncias e o log de auditoria da Comunidade. Para
voltar atrás é preciso restaurar um backup da base de dados anterior a este
upgrade.
"""
from alembic import op
import sqlalchemy as sa


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


def upgrade():
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
