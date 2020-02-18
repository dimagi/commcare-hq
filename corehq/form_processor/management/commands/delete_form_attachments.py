from django.core.management.base import BaseCommand

from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.dbaccessors import FormAccessors


class Command(BaseCommand):
    help = "Delete form attachments matching filter, for use upon client request."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--xmlns', required=True)
        parser.add_argument('--app-id', required=True)
        parser.add_argument('--xform-ids', help='Comma-separated xform ids')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, xmlns, app_id, dry_run, xform_ids, **options):
        accessor = FormAccessors(domain)
        if xform_ids:
            form_ids = xform_ids.split(',')
        else:
            form_ids = accessor.iter_form_ids_by_xmlns(xmlns)
        attachments_to_delete = []
        for form_id in form_ids:
            form = accessor.get_with_attachments(form_id)
            if form.domain != domain or form.xmlns != xmlns or form.app_id != app_id:
                continue
            print(f'{form_id}\t{",".join(form.attachments) or "No attachments to delete"}')
            for name, blob_meta in form.attachments.items():
                attachments_to_delete.append((form_id, name, blob_meta))

        if not dry_run:
            if input("Delete all the above attachments? [y/n]").lower() in ('y', 'yes'):
                for form_id, name, blob_meta in attachments_to_delete:
                    print(f'Deleting {form_id}/{name} ({blob_meta.key})')
                    # todo: if this is ever too slow, we can bulk delete instead
                    # https://github.com/dimagi/commcare-hq/pull/26672#discussion_r380522955
                    get_blob_db().delete(blob_meta.key)
