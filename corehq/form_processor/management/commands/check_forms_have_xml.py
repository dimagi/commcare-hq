import csv
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
        parser.add_argument('domains', nargs="*", help='Domains to check.')
        parser.add_argument('file_name', help='Location to put the output.')

    def handle(self, domains, file_name, **options):
        blob_db = get_blob_db()

        with open(file_name, 'w', encoding='utf-8') as csv_file:
            field_names = ['domain', 'archived', 'form_id', 'received_on']
            csv_writer = csv.DictWriter(csv_file, field_names)
            csv_writer.writeheader()
            for domain in domains:
                self.stdout.write("Handling domain %s" % domain)
                form_db = FormAccessors(domain)
                form_ids = form_db.get_all_form_ids_in_domain()
                form_ids.extend(form_db.get_all_form_ids_in_domain('XFormArchived'))
                for form in with_progress_bar(form_db.iter_forms(form_ids), len(form_ids)):
                    if isinstance(form, CouchForm):
                        meta = form.blobs.get(ATTACHMENT_NAME)
                        if not meta or not blob_db.exists(key=meta.key):
                            self.write_row(csv_writer, domain, form.is_archived, form.received_on, form.form_id)
                    elif isinstance(form, XFormInstanceSQL):
                        meta = form.get_attachment_meta(ATTACHMENT_NAME)
                        if not meta or not blob_db.exists(key=meta.key):
                            self.write_row(csv_writer, domain, form.is_archived, form.received_on, form.form_id)
                    else:
                        raise Exception("not sure how we got here")

    @staticmethod
    def write_row(writer, domain, archived, received_on, form_id):
        properties = {
            'domain': domain,
            'archived': archived,
            'received_on': received_on,
            'form_id': form_id,
        }
        writer.writerow(properties)
