from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import uuid

from django.core.management.base import BaseCommand

from corehq.form_processor.models import XFormAttachmentSQL
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class Command(BaseCommand):
    help = """Copy attachments from deprecated forms to the edited form.
    See https://github.com/dimagi/commcare-hq/pull/17337 for more details
    """

    def handle(self, *args, **options):

        seen_forms = set()
        for db_name in get_db_aliases_for_partitioned_query():
            deprecated_form_ids = XFormAttachmentSQL.objects.using(db_name).filter(
                form__orig_id__isnull=False,
                form__state=XFormInstanceSQL.DEPRECATED
            ).exclude(
                name='form.xml'
            ).values_list('form_id', flat=True).all()

            for form_id in deprecated_form_ids:
                if form_id in seen_forms:
                    continue

                deprecated_form = XFormInstanceSQL.objects.partitioned_get(form_id)
                seen_forms.add(form_id)
                seen_forms.add(deprecated_form.orig_id)

                print(('checking form, deprecated_form_id, ', form_id, 'orig_form_id, ', deprecated_form.orig_id))

                new_form = XFormInstanceSQL.objects.partitioned_get(deprecated_form.orig_id)
                copy_attachments(deprecated_form, new_form)


def copy_attachments(from_form, to_form):
    to_form_attachments = to_form.attachments
    for name, att in from_form.attachments.items():
        if name in to_form_attachments:
            # populate missing fields
            print(('updating attachment, name, ', name, 'form_id, ', to_form.form_id))
            att_new = to_form_attachments[name]
            att_new.content_length = att.content_length
            att_new.blob_bucket = att.blobdb_bucket()
            att_new.save()
        else:
            print(('creating attachment, name, ', name, 'form_id, ', to_form.form_id))
            XFormAttachmentSQL(
                name=att.name,
                attachment_id=uuid.uuid4(),
                content_type=att.content_type,
                content_length=att.content_length,
                properties=att.properties,
                blob_id=att.blob_id,
                blob_bucket=att.blobdb_bucket(),
                md5=att.md5,
                form_id=to_form.form_id
            ).save()
