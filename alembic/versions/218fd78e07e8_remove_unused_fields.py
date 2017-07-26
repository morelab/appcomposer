"""Remove unused fields

Revision ID: 218fd78e07e8
Revises: 271e8b4e3c8d
Create Date: 2017-07-25 01:17:38.884111

"""

# revision identifiers, used by Alembic.
revision = '218fd78e07e8'
down_revision = '271e8b4e3c8d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(u'ix_RepositoryApp2languages_downloaded_hash', table_name='RepositoryApp2languages')
    op.drop_index(u'ix_RepositoryApp2languages_error', table_name='RepositoryApp2languages')
    op.drop_index(u'ix_RepositoryApp2languages_last_processed_hash', table_name='RepositoryApp2languages')
    op.drop_index(u'ix_RepositoryApp2languages_last_processed_time', table_name='RepositoryApp2languages')
    op.drop_column('RepositoryApp2languages', u'last_processed_hash')
    op.drop_column('RepositoryApp2languages', u'last_processed_time')
    op.drop_column('RepositoryApp2languages', u'downloaded_hash')
    op.drop_column('RepositoryApp2languages', u'error')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('RepositoryApp2languages', sa.Column(u'error', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True))
    op.add_column('RepositoryApp2languages', sa.Column(u'downloaded_hash', mysql.VARCHAR(length=255), nullable=True))
    op.add_column('RepositoryApp2languages', sa.Column(u'last_processed_time', sa.DATETIME(), nullable=True))
    op.add_column('RepositoryApp2languages', sa.Column(u'last_processed_hash', mysql.VARCHAR(length=255), nullable=True))
    op.create_index(u'ix_RepositoryApp2languages_last_processed_time', 'RepositoryApp2languages', [u'last_processed_time'], unique=False)
    op.create_index(u'ix_RepositoryApp2languages_last_processed_hash', 'RepositoryApp2languages', [u'last_processed_hash'], unique=False)
    op.create_index(u'ix_RepositoryApp2languages_error', 'RepositoryApp2languages', [u'error'], unique=False)
    op.create_index(u'ix_RepositoryApp2languages_downloaded_hash', 'RepositoryApp2languages', [u'downloaded_hash'], unique=False)
    ### end Alembic commands ###