import csv
import logging
from datetime import datetime

from django.core.management.base import BaseCommand

from casexml.apps.case.xform import get_case_ids_from_form
from corehq.form_processor.models import XFormInstance
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Output all case IDs from the given form IDs"

    def add_arguments(self, parser):
        parser.add_argument('file_path', help='Path to the list of form IDs. One ID per line.')

    def handle(self, file_path, **options):
        with open(file_path, 'r') as f:
            form_ids = [line.strip() for line in f.readlines()]

        output_path = f"case_ids_{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S', )}.csv"
        print(f"Writing data to {output_path}")
        with open(output_path, 'w') as out:
            writer = csv.writer(out)
            writer.writerow(["form_id", "case_id"])
            for form_id, case_ids in _get_case_ids(with_progress_bar(form_ids)):
                for case_id in case_ids:
                    writer.writerow([form_id, case_id])


def _get_case_ids(form_ids):
    for form_id_chunk in chunked(form_ids, 100):
        form_id_chunk = list(form_id_chunk)
        try:
            forms = XFormInstance.objects.get_forms_with_attachments_meta(form_id_chunk)
        except Exception:
            logger.exception("Error fetching bulk forms")
            for form_id in form_id_chunk:
                try:
                    form = XFormInstance.objects.get_form(form_id)
                except Exception as e:
                    yield form_id, [f"Unable to get form: {e}"]
                else:
                    yield form.form_id, get_case_ids_from_form(form)
        else:
            for form in forms:
                yield form.form_id, get_case_ids_from_form(form)
