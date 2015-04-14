"""Add datetime also to ActiveTranslation

Revision ID: 6d09f595667
Revises: f62656baeb0
Create Date: 2015-04-12 07:02:06.793959

"""

# revision identifiers, used by Alembic.
revision = '6d09f595667'
down_revision = 'f62656baeb0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    try:
        op.add_column('ActiveTranslationMessages', sa.Column('datetime', sa.DateTime(), nullable=True))
        op.create_index(u'ix_ActiveTranslationMessages_datetime', 'ActiveTranslationMessages', ['datetime'], unique=False)
    except:
        print "Already added previously"
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(u'ix_ActiveTranslationMessages_datetime', table_name='ActiveTranslationMessages')
    op.drop_column('ActiveTranslationMessages', 'datetime')
    ### end Alembic commands ###
