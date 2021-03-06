"""Add TranslationExternalSuggestions

Revision ID: 2ef3688b5383
Revises: 20860ffde766
Create Date: 2015-04-19 12:43:34.752894

"""

# revision identifiers, used by Alembic.
revision = '2ef3688b5383'
down_revision = '20860ffde766'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('TranslationExternalSuggestions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('engine', sa.Unicode(length=20), nullable=True),
    sa.Column('human_key', sa.Unicode(length=255), nullable=True),
    sa.Column('language', sa.Unicode(length=255), nullable=True),
    sa.Column('value', sa.UnicodeText(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('engine', 'human_key', 'language')
    )
    op.create_index(u'ix_TranslationExternalSuggestions_engine', 'TranslationExternalSuggestions', ['engine'], unique=False)
    op.create_index(u'ix_TranslationExternalSuggestions_human_key', 'TranslationExternalSuggestions', ['human_key'], unique=False)
    op.create_index(u'ix_TranslationExternalSuggestions_language', 'TranslationExternalSuggestions', ['language'], unique=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(u'ix_TranslationExternalSuggestions_language', table_name='TranslationExternalSuggestions')
    op.drop_index(u'ix_TranslationExternalSuggestions_human_key', table_name='TranslationExternalSuggestions')
    op.drop_index(u'ix_TranslationExternalSuggestions_engine', table_name='TranslationExternalSuggestions')
    op.drop_table('TranslationExternalSuggestions')
    ### end Alembic commands ###
