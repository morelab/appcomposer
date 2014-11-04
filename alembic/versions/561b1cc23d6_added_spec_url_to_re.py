"""Added spec_url to replace spec appvar

Revision ID: 561b1cc23d6
Revises: 4211b3736e90
Create Date: 2014-11-04 09:57:23.710248

"""


# revision identifiers, used by Alembic.
import json
from appcomposer.models import App

revision = '561b1cc23d6'
down_revision = '4211b3736e90'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Apps', sa.Column('spec_url', sa.Unicode(length=600), nullable=True))
    ### end Alembic commands ###

    # To upgrade we need to take every AppVar with spec, remove it, and add it to the App itself.
    op.execute("UPDATE Apps SET spec_url = (SELECT value FROM AppVars WHERE name = 'spec' and app_id = Apps.id)")
    op.execute("DELETE FROM AppVars WHERE name = 'spec'")

    # We will also try to extract the spec from the JSON data when possible.
    connection = op.get_bind()
    oldapp_ids = connection.execute("SELECT id, data FROM Apps WHERE spec_url IS NULL")
    for oldapp_id, data in oldapp_ids:
        try:
            data = json.loads(data)
            spec = data["spec"]
            op.execute(
                App.update().where(id==op.inline_literal(oldapp_id)).values({"spec_url": op.inline_literal(spec)})
            )
        except:
            print "Exception on an app: %r" % oldapp_id
            
def downgrade():

    # To downgrade we need to add an AppVar with the spec to every App.
    op.execute("INSERT INTO AppVars (name, value) SELECT 'spec', spec_url FROM Apps")

    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('Apps', 'spec_url')
    ### end Alembic commands ###
