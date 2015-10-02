from datetime import date
from celery.schedules import crontab
from celery.task import periodic_task
from django.core.management import call_command
from corehq.util.soft_assert import soft_assert
from .models import BackupRecord

import settings

GUINEA_CONTACT_TRACING_DOMAIN = 'guinea_contact_tracing'
GUINEA_CONTACT_TRACING_DATABASE = 'guineact-backup'


@periodic_task(run_every=crontab(minute="0", hour="1", day_of_week="0"), queue='background_queue')
def copy_data_to_backup():
    if settings.SERVER_ENVIRONMENT == 'production':
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
        last_update = BackupRecord.objects.order_by('last_update')[0].last_update

        call_command('copy_domain',
                     prod_couchdb_connection,
                     GUINEA_CONTACT_TRACING_DOMAIN,
                     guinea_couchdb_connection,
                     **{'since': unicode(last_update)})

        # A dumb soft assert to make sure I see this working
        _assert = soft_assert(to='{}@{}'.format('tsheffels', 'dimagi.com'),
                              notify_admins=False,
                              exponential_backoff=False)
        _assert(False)

        successful_insert = BackupRecord(last_update=date.now())
        successful_insert.save()
