import datetime
import logging

from django.core.management.base import BaseCommand

from corehq.apps.es import filters
from corehq.apps.es.forms import FormES
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL

logger = logging.getLogger('main')


class Command(BaseCommand):
    help = "Overwrites blob_bucket for attachments that aren't the default"

    def handle(self, *args, **options):
        possible_bad_forms = (
            FormES()
            .submitted(
                gte=datetime.date(2016, 10, 14),
                lt=datetime.date(2016, 10, 20),
            )
            .filter(filters.term('backend_id', 'sql'))
            .source('_id')
        ).run().hits

        form_ids = [form['_id'] for form in possible_bad_forms]
        blob_db = get_blob_db()

        for form_id in form_ids:
            form = FormAccessorSQL.get_form(form_id)
            for attachment in form.get_attachments():
                if attachment.blob_bucket:
                    continue

                bucket = attachment.blobdb_bucket(remove_dashes=False)
                attach_id = str(attachment.attachment_id)
                if blob_db.exists(attachment.blob_id, bucket):
                    FormAccessorSQL.write_blob_bucket(attachment, bucket)
                    logging.info(attach_id + " overwritten blob_bucket_succesfully")
                else:
                    # This is the default and what we want long term
                    # verify it exists
                    bucket = attachment.blobdb_bucket(remove_dashes=True)
                    if not blob_db.exists(attachment.blob_id, bucket):
                        logger.error(attach_id + " does not exist in either expected bucket")
