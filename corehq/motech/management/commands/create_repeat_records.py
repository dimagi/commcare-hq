import logging
import re

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.motech.repeaters.management.commands.find_missing_repeat_records import (
    get_repeaters_for_type_in_domain,
)
from corehq.motech.repeaters.models import Repeater, get_all_repeater_types
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Command(BaseCommand):

    help = "Create repeat records for cases and forms"

    def add_arguments(self, parser):
        parser.add_argument('file_path', help='Path to the list of IDs. One ID per line.')
        parser.add_argument('-t', '--doc-type', choices=['form', 'case'])
        parser.add_argument('--repeater-type', choices=get_all_repeater_types(),
                            help='Only create records for this repeater type')
        parser.add_argument('--repeater-id', help='Only create records for this repeater')
        parser.add_argument('--repeater-name',
                            help='Only create records for repeaters whose name matches this regex')

    def handle(self, file_path, *args, **options):
        with open(file_path, 'r') as file:
            doc_ids = [line.strip() for line in file.readlines()]

        repeater_type = options['repeater_type']
        repeater_id = options['repeater_id']
        repeater_name_re = None
        if options['repeater_name']:
            repeater_name_re = re.compile(options['repeater_name'])

        if repeater_id:
            repeater = Repeater.objects.get(id=repeater_id)
            if repeater_type and repeater_type != repeater.repeater_type:
                raise CommandError(f"Repeater type does not match: {repeater_type} != {repeater.repeater_type}")
            if repeater_name_re and not repeater_name_re.match(repeater.name):
                raise CommandError(f"Repeater name does not match: {repeater.name}")

            def _get_repeaters(doc):
                assert doc.domain == repeater.domain
                return [repeater]
        else:
            by_domain = {}

            def _get_repeaters(doc):
                if doc.domain not in by_domain:
                    repeater_class = get_all_repeater_types()[repeater_type] if repeater_type else None
                    repeaters = get_repeaters_for_type_in_domain(doc.domain, [repeater_class._repeater_type])
                    if repeater_name_re:
                        repeaters = [r for r in repeaters if repeater_name_re.match(r.name)]

                    if not repeaters:
                        logger.info(f"No repeaters matched for domain '{doc.domain}'")
                    by_domain[doc.domain] = repeaters
                return by_domain[doc.domain]

        def doc_iterator(doc_ids):
            try:
                yield from bulk_accessor(doc_ids)
            except Exception:
                logger.exception("Unable to fetch bulk docs, falling back to individual fetches")
                for doc_id in doc_ids:
                    try:
                        yield single_accessor(doc_id)
                    except Exception:
                        logger.exception(f"Unable to fetch doc '{doc_id}'")

        forms = XFormInstance.objects
        cases = CommCareCase.objects
        bulk_accessor = forms.get_forms if options['doc_type'] == 'form' else cases.get_cases
        single_accessor = forms.get_form if options['doc_type'] == 'form' else cases.get_case
        for doc_ids in chunked(with_progress_bar(doc_ids), 100):
            for doc in doc_iterator(list(doc_ids)):
                try:
                    repeaters = _get_repeaters(doc)
                except Exception:
                    logger.exception(f"Unable to fetch repeaters for doc '{doc.get_id}'")
                    continue

                for repeater in repeaters:
                    try:
                        repeater.register(doc)
                    except Exception:
                        logger.exception(f"Unable to create records for doc '{doc.get_id}'")
