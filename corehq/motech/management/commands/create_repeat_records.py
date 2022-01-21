import logging
import re

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.motech.repeaters.management.commands.find_missing_repeat_records import (
    get_repeaters_for_type_in_domain,
)
from corehq.motech.repeaters.models import Repeater, get_all_repeater_types
from corehq.util.log import with_progress_bar

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
            repeater = Repeater.get(repeater_id)
            if repeater_type and repeater_type != repeater.doc_type:
                raise CommandError(f"Repeater type does not match: {repeater_type} != {repeater.doc_type}")
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
                    repeaters = get_repeaters_for_type_in_domain(doc.domain, repeater_class)
                    if repeater_name_re:
                        repeaters = [r for r in repeaters if repeater_name_re.match(r.name)]

                    if not repeaters:
                        logger.info(f"No repeaters matched for domain '{doc.domain}'")
                    by_domain[doc.domain] = repeaters
                return by_domain[doc.domain]

        accessor = FormAccessorSQL.get_form if options['doc_type'] == 'form' else CaseAccessorSQL.get_case
        for doc_id in with_progress_bar(doc_ids):
            try:
                form_or_case = accessor(doc_id)
                for repeater in _get_repeaters(form_or_case):
                    repeater.register(form_or_case)
            except Exception:
                logger.exception(f"Unable to process doc '{doc_id}")
