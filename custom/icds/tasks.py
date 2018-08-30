from __future__ import absolute_import
from __future__ import unicode_literals

import os

from datetime import timedelta, datetime
from celery.schedules import crontab
from celery.task import periodic_task
from celery.task import task
from django.conf import settings
from corehq.blobs import get_blob_db
from corehq.form_processor.models import XFormAttachmentSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.datadog.gauges import datadog_counter
from django.core.mail.message import EmailMessage
from custom.icds.translations.integrations.transifex import Transifex
from io import open

if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
    @periodic_task(serializer='pickle', run_every=crontab(minute=0, hour='22'))
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
def delete_resources_on_transifex(domain, data, email):
    version = data.get('version')
    transifex = Transifex(domain,
                          data.get('app_id'),
                          data.get('target_lang') or data.get('source_lang'),
                          data.get('transifex_project_slug'),
                          version,
                          use_version_postfix='yes' in data['use_version_postfix'])
    delete_status = transifex.delete_resources()
    result_note = "Hi,\nThe request to delete resources for app {app_id}(version {version}), " \
                  "was completed on project {transifex_project_slug} on transifex. " \
                  "The result is as follows:\n".format(**data)
    email = EmailMessage(
        subject='[{}] - Transifex removed translations'.format(settings.SERVER_ENVIRONMENT),
        body=(result_note +
              "\n".join([' '.join([sheet_name, result]) for sheet_name, result in delete_status.items()])
              ),
        to=[email],
        from_email=settings.DEFAULT_FROM_EMAIL
    )
    email.send()


@task
def push_translation_files_to_transifex(domain, data, email):
    upload_status = None
    if data.get('target_lang'):
        upload_status = Transifex(domain,
                                  data.get('app_id'),
                                  data.get('target_lang'),
                                  data.get('transifex_project_slug'),
                                  data.get('version'),
                                  is_source_file=False,
                                  exclude_if_default=True,
                                  use_version_postfix='yes' in data['use_version_postfix']
                                  ).send_translation_files()
    elif data.get('source_lang'):
        upload_status = Transifex(domain,
                                  data.get('app_id'),
                                  data.get('source_lang'),
                                  data.get('transifex_project_slug'),
                                  data.get('version'),
                                  use_version_postfix='yes' in data['use_version_postfix'],
                                  update_resource='yes' in data['update_resource']
                                  ).send_translation_files()
    if upload_status:
        result_note = "Hi,\nThe upload for app {app_id}(version {version}), " \
                      "with source language '{source_lang}' and target lang '{target_lang}' " \
                      "was completed on project {transifex_project_slug} on transifex. " \
                      "The result is as follows:\n".format(**data)
        email = EmailMessage(
            subject='[{}] - Transifex pushed translations'.format(settings.SERVER_ENVIRONMENT),
            body=(result_note +
                  "\n".join([' '.join([sheet_name, result]) for sheet_name, result in upload_status.items()])
                  ),
            to=[email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()


@task
def pull_translation_files_from_transifex(domain, data, email=None):
    version = data.get('version')
    transifex = Transifex(domain,
                          data.get('app_id'),
                          data.get('target_lang') or data.get('source_lang'),
                          data.get('transifex_project_slug'),
                          version,
                          lock_translations=data.get('lock_translations'),
                          use_version_postfix='yes' in data['use_version_postfix'])
    translation_file = None
    try:
        translation_file, filename = transifex.generate_excel_file()
        with open(translation_file.name, 'rb') as file_obj:
            email = EmailMessage(
                subject='[{}] - Transifex pulled translations'.format(settings.SERVER_ENVIRONMENT),
                body="PFA Translations pulled from transifex.",
                to=[email],
                from_email=settings.DEFAULT_FROM_EMAIL
            )
            email.attach(filename=filename, content=file_obj.read())
            email.send()
    finally:
        if translation_file and os.path.exists(translation_file.name):
            os.remove(translation_file.name)
