from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from django.core.management.base import BaseCommand
from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import XFormInstanceSQL
from corehq.util.log import with_progress_bar
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance as CouchForm


class Command(BaseCommand):
    help = "Check if there is form.xml in all forms for a domain."

    def add_arguments(self, parser):
        parser.add_argument('domain', help='Domain to check.')
        parser.add_argument('file_name', help='Location to put the output.')

    def handle(self, domain, file_name, **options):
        blob_db = get_blob_db()
        form_db = FormAccessors(domain)
        form_ids = form_db.get_all_form_ids_in_domain()
        with open(file_name, 'w') as open_file:
            for form in with_progress_bar(form_db.iter_forms(form_ids), len(form_ids)):
                if isinstance(form, CouchForm):
                    meta = form.blobs.get(ATTACHMENT_NAME)
                    if not meta or not blob_db.exists(
                            meta.id, form._blobdb_bucket()):  # pylint: disable=protected-access
                        open_file.write(form.form_id)
                elif isinstance(form, XFormInstanceSQL):
                    meta = form.get_attachment_meta(ATTACHMENT_NAME)
                    if not meta or not blob_db.exists(meta.blob_id, meta.blobdb_bucket()):
                        open_file.write(form.form_id)
                else:
                    raise Exception("not sure how we got here")
