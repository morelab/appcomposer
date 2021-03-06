"""Avoid duplications in suggestions

Revision ID: dfc939482d8d
Revises: d3f9c4829e4a
Create Date: 2017-10-14 22:31:37.153990

"""

# revision identifiers, used by Alembic.
revision = 'dfc939482d8d'
down_revision = 'd3f9c4829e4a'

from collections import defaultdict

from alembic import op
import sqlalchemy as sa

from sqlalchemy import func

from appcomposer.db import db
from appcomposer.application import app

metadata = db.MetaData()
TranslationExternalSuggestion = db.Table('TranslationExternalSuggestions', metadata,
    sa.Column('id', sa.Integer, nullable=True),
    sa.Column('engine', sa.Unicode(length=255), nullable=True),
    sa.Column('language', sa.Integer, nullable=False),
    sa.Column('human_key_hash', sa.Integer, nullable=False),
)

def upgrade():
    with app.app_context():
        duplicated_suggestions = list(db.session.query(TranslationExternalSuggestion.c.engine, TranslationExternalSuggestion.c.language, TranslationExternalSuggestion.c.human_key_hash).group_by(TranslationExternalSuggestion.c.engine, TranslationExternalSuggestion.c.language, TranslationExternalSuggestion.c.human_key_hash).having(func.count(TranslationExternalSuggestion.c.id) > 1).all())

        engines = [ engine for engine, language, human_key_hash in duplicated_suggestions ]
        languages = [ language for engine, language, human_key_hash in duplicated_suggestions ]
        human_key_hashes = [ human_key_hash for engine, language, human_key_hash in duplicated_suggestions ]

        all_results = defaultdict(list)
        for suggestion in db.session.query(TranslationExternalSuggestion).filter(TranslationExternalSuggestion.c.engine.in_(engines), TranslationExternalSuggestion.c.language.in_(languages), TranslationExternalSuggestion.c.human_key_hash.in_(human_key_hashes)).all():
            all_results[suggestion.engine, suggestion.language, suggestion.human_key_hash].append(suggestion)

        all_ids = []
        for engine, language, human_key_hash in duplicated_suggestions:
            for suggestion in all_results[engine, language, human_key_hash][1:]:
                all_ids.append(suggestion.id)

    delete_stmt = TranslationExternalSuggestion.delete(TranslationExternalSuggestion.c.id.in_(all_ids))
    connection = op.get_bind()
    connection.execute(delete_stmt)



    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'TranslationExternalSuggestions', ['engine', 'human_key_hash', 'language'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'TranslationExternalSuggestions', type_='unique')
    # ### end Alembic commands ###
