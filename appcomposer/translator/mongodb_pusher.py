from datetime import timedelta, datetime
import json
import os

from celery import Celery
from celery.utils.log import get_task_logger
from bson import json_util
from pymongo import MongoClient
from sqlalchemy.orm import joinedload

# Fix the working directory when running from the script's own folder.
from pymongo.errors import DuplicateKeyError
import sys

cwd = os.getcwd()
path = os.path.join("appcomposer", "composers", "translate")
if cwd.endswith(path):
    cwd = cwd[0:len(cwd) - len(path)]
    os.chdir(cwd)

sys.path.insert(0, cwd)

from appcomposer import db
from appcomposer.application import app as flask_app
from appcomposer.models import TranslationUrl, TranslationBundle

# Fix the path so it can be run more easily, etc.
from appcomposer.composers.translate.db_helpers import _db_get_diff_specs, _db_get_ownerships, load_appdata_from_db


MONGODB_SYNC_PERIOD = flask_app.config.get("MONGODB_SYNC_PERIOD", 60*10)  # Every 10 min by default.

cel = Celery('pusher_tasks', backend='amqp', broker='amqp://')
cel.conf.update(
    CELERYD_PREFETCH_MULTIPLIER="4",
    CELERYD_CONCURRENCY="8",
    CELERY_ACKS_LATE="1",
    CELERY_IGNORE_RESULT=True,

    CELERYBEAT_SCHEDULE = {
        'sync-periodically': {
            'task': 'sync',
            'schedule': timedelta(seconds=MONGODB_SYNC_PERIOD),
            'args': ()
        }
    }
)

mongo_client = MongoClient(flask_app.config["MONGODB_PUSHES_URI"])
mongo_db = mongo_client.appcomposerdb
mongo_bundles = mongo_db.bundles
mongo_translation_urls = mongo_db.translation_urls

logger = get_task_logger(__name__)

def retrieve_mongodb_contents():
    bundles_results = [ result for result in mongo_bundles.find() ]
    bundles_serialized = json.dumps(bundles_results, default=json_util.default)

    translations_url_results = [ result for result in mongo_translation_urls.find() ]
    translations_url_serialized = json.dumps(translations_url_results, default=json_util.default)

    return { 'bundles' : json.loads(bundles_serialized), 'translation_urls' : json.loads(translations_url_serialized) }

@cel.task(name="push", bind=True)
def push(self, translation_url, lang, target):
    try:
        logger.info("[PUSH] Pushing to %s@%s" % (lang, translation_url))

        with flask_app.app_context():
            translation_bundle = db.session.query(TranslationBundle).filter(TranslationBundle.translation_url_id == TranslationUrl.id, TranslationUrl.url == translation_url, TranslationBundle.language == lang, TranslationBundle.target == target).options(joinedload("translation_url")).first()
            payload = {}
            max_date = datetime(1970, 1, 1)
            for message in translation_bundle.active_messages:
                payload[message.key] = message.value
                if message.datetime > max_date:
                    max_date = message.datetime
            data = json.dumps(payload)

            lang_pack = lang + '_' + target

            bundle_id = lang_pack + '::' + translation_url
            bundle = { '_id' : bundle_id, 'url' : translation_url,  'bundle' : lang_pack, 'data' : data, 'time' : max_date }
            try:
                mongo_translation_urls.update({'_id' : bundle_id, 'time' : { '$lt' : max_date }}, bundle, upsert = True)
                logger.info("[PUSH]: Updated translation URL bundle %s" % bundle_id)
            except DuplicateKeyError:
                logger.info("[PUSH]: Ignoring push for translation URL bundle %s (newer date exists already)" % bundle_id)
            
            app_bundle_ids = []
            for application in translation_bundle.translation_url.apps:
                bundle_id = lang_pack + '::' + application.url
                app_bundle_ids.append(bundle_id)
                bundle = { '_id' : bundle_id, 'spec' : application.url,  'bundle' : lang_pack, 'data' : data, 'time' : max_date }
                try:
                    mongo_bundles.update({'_id' : bundle_id, 'time' : { '$lt' : max_date }}, bundle, upsert = True)
                    logger.info("[PUSH]: Updated application bundle %s" % bundle_id)
                except DuplicateKeyError:
                    logger.info("[PUSH]: Ignoring push for application bundle %s (newer date exists already)" % bundle_id)

            return bundle_id, app_bundle_ids
    except Exception as exc:
        logger.warn("[PUSH]: Exception occurred. Retrying soon.")
        raise self.retry(exc=exc, default_retry_delay=60, max_retries=None)

@cel.task(name="sync", bind=True)
def sync(self):
    """
    Fully synchronizes the local database leading translations with
    the MongoDB.
    """
    logger.info("[SYNC]: Starting Sync task")

    start_time = datetime.utcnow()

    with flask_app.app_context():
        translation_bundles = [ {
                'translation_url' : bundle.translation_url.url,
                'language' : bundle.language,
                'target' : bundle.target
            } for bundle in db.session.query(TranslationBundle).options(joinedload("translation_url")).all() ]
    
    all_translation_url_ids = []
    all_app_ids = []

    for translation_bundle in translation_bundles:
        translation_url_id, app_ids = push(translation_url = translation_bundle['translation_url'], lang = translation_bundle['language'], target = translation_bundle['target'])
        all_translation_url_ids.append(translation_url_id)
        all_app_ids.extend(app_ids)
    
    mongo_bundles.remove({"_id": {"$nin": all_app_ids}, "time": {"$lt": start_time}})
    mongo_translation_urls.remove({"_id": {"$nin": all_translation_url_ids}, "time": {"$lt": start_time}})

    logger.info("[SYNC]: Sync finished.")

if __name__ == '__main__':
    cel.worker_main(sys.argv)