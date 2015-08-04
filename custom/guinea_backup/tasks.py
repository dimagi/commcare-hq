from datetime import timedelta
from celery.task import periodic_task
from corehq.apps.domainsync.management.commands.copy_domain import Command

import settings

GUINEA_CONTACT_TRACING_DOMAIN = 'guinea_contact_tracing'
GUINEA_CONTACT_TRACING_DATABASE = 'guineact-backup'

# @periodic_task(run_every=timedelta(days=7), queue=settings.CELERY_PERIODIC_QUEUE)
def copy_data_to_backup():
    # BackupLog.find(order_by: date desc)

    # https://<your_username>:<your_password>@commcarehq.cloudant.com/commcarehq
    prod_couchdb_connection = 'https://{username}:{password}@commcarehq.cloudant.com/{database}'.format(
        username=settings.COUCH_USERNAME,
        password=settings.COUCH_PASSWORD,
        database=settings.COUCH_DATABASE_NAME,
    )
    guinea_couchdb_connection = 'https://{username}:{password}@commcarehq.cloudant.com/{database}'.format(
        username=settings.COUCH_USERNAME,
        password=settings.COUCH_PASSWORD,
        database=GUINEA_CONTACT_TRACING_DATABASE,
    )

    args = [
        prod_couchdb_connection,
        GUINEA_CONTACT_TRACING_DOMAIN,
        guinea_couchdb_connection
    ]
    kwargs = {
        'since': '2015-07-30',  

    }
    Command.handle(args=args, kwargs=kwargs)
