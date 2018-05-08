from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta, datetime
from celery.schedules import crontab
from celery.task import periodic_task
from celery.task import task
from django.conf import settings
from corehq.blobs import get_blob_db
from corehq.form_processor.models import XFormAttachmentSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.datadog.gauges import datadog_counter
from custom.icds.translations.integrations.transifex import Transifex

if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
    @periodic_task(run_every=crontab(minute=0, hour='22'))
    def delete_old_images():
        start = datetime.utcnow()
        max_age = start - timedelta(days=90)
        db = get_blob_db()

        def _get_query(db_name, max_age=max_age):
            return XFormAttachmentSQL.objects.using(db_name).filter(
                content_type='image/jpeg',
                form__domain='icds-cas',
                form__received_on__lt=max_age
            )

        run_again = False
        for db_name in get_db_aliases_for_partitioned_query():
            paths = []
            deleted_attachments = []
            bytes_deleted = 0
            attachments = _get_query(db_name)
            for attachment in attachments[:1000]:
                paths.append(db.get_path(attachment.blob_id, attachment.blobdb_bucket()))
                deleted_attachments.append(attachment.pk)
                bytes_deleted += attachment.content_length if attachment.content_length else 0

            if paths:
                db.bulk_delete(paths)
                XFormAttachmentSQL.objects.using(db_name).filter(pk__in=deleted_attachments).delete()
                datadog_counter('commcare.icds_images.bytes_deleted', value=bytes_deleted)
                datadog_counter('commcare.icds_images.count_deleted', value=len(paths))
                run_again = True

        if run_again:
            delete_old_images.delay()


@task
def send_translation_files_to_transifex(domain, form_data):
    Transifex(domain, form_data.get('app_id'),
              form_data.get('source_lang'),
              form_data.get('target_lang'),
              form_data.get('version')).send_files_to_transifex()