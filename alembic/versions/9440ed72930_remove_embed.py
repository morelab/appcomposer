"""Remove Embed

Revision ID: 9440ed72930
Revises: 24b650b60652
Create Date: 2017-05-10 16:53:41.661465

"""

# revision identifiers, used by Alembic.
revision = '9440ed72930'
down_revision = '24b650b60652'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table(u'EmbedApplicationTranslation')
    op.drop_table(u'EmbedApplications')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table(u'EmbedApplications',
    sa.Column(u'id', mysql.INTEGER(display_width=11), nullable=False),
    sa.Column(u'url', mysql.VARCHAR(length=255), nullable=False),
    sa.Column(u'name', mysql.VARCHAR(length=100), nullable=False),
    sa.Column(u'owner_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column(u'identifier', mysql.VARCHAR(length=36), nullable=False),
    sa.Column(u'creation', sa.DATETIME(), nullable=False),
    sa.Column(u'last_update', sa.DATETIME(), nullable=False),
    sa.Column(u'height', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column(u'scale', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint([u'owner_id'], [u'GoLabOAuthUsers.id'], name=u'EmbedApplications_ibfk_1'),
    sa.PrimaryKeyConstraint(u'id'),
    mysql_default_charset=u'utf8',
    mysql_engine=u'InnoDB'
    )
    op.create_table(u'EmbedApplicationTranslation',
    sa.Column(u'id', mysql.INTEGER(display_width=11), nullable=False),
    sa.Column(u'embed_application_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column(u'url', mysql.VARCHAR(length=255), nullable=False),
    sa.Column(u'language', mysql.VARCHAR(length=10), nullable=False),
    sa.ForeignKeyConstraint([u'embed_application_id'], [u'EmbedApplications.id'], name=u'EmbedApplicationTranslation_ibfk_1'),
    sa.PrimaryKeyConstraint(u'id'),
    mysql_default_charset=u'utf8',
    mysql_engine=u'InnoDB'
    )
    ### end Alembic commands ###
