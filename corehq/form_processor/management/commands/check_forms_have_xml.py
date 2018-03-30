from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.models import XFormInstanceSQL
from corehq.util.log import with_progress_bar
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance as CouchForm
import datetime
import logging

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check if there is form.xml in all forms for a domain."

    def add_arguments(self, parser):
        parser.add_argument('domain', help='Domain to check.')

    def handle(self, domain, **options):
        blob_db = get_blob_db()
        form_db = FormAccessors(domain)
        form_ids = form_db.get_all_form_ids_in_domain()
        bad_form_id_string = "%s %s: %%s" % (domain, datetime.datetime.utcnow())
        for form in with_progress_bar(form_db.iter_forms(form_ids), len(form_ids)):
            if isinstance(form, CouchForm):
                meta = form.blobs.get(ATTACHMENT_NAME)
                if not meta or not blob_db.exists(
                        meta.id, meta._blobdb_bucket()):  # pylint: disable=protected-access
                    _logger.info(bad_form_id_string, form.form_id)
            elif isinstance(form, XFormInstanceSQL):
                meta = form.get_attachment_meta(ATTACHMENT_NAME)
                if not meta or not blob_db.exists(meta.blob_id, meta.blobdb_bucket()):
                    _logger.info(bad_form_id_string, form.form_id)
            else:
                raise Exception("not sure how we got here")
