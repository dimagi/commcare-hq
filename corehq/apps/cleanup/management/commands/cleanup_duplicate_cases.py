from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from datetime import datetime
from io import open

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory, CaseStructure
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.util.log import with_progress_bar

DOMAIN = 'mukte-ii'


def log(message):
    with open('cleanup_duplicate_cases.log', 'a') as f:
        f.write(message)
        f.write('\n')


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'case_ids',
            nargs='*',
        )
        parser.add_argument(
            '--close-cases',
            action='store_true',
            default=False,
        )

    def handle(self, case_ids, **options):
        close_cases = options['close_cases']
        case_ids = case_ids or self._get_case_ids()
        cases = self.accessor.get_cases(case_ids)
        for case in with_progress_bar(cases):
            if self.is_duplicate(case):
                log('Flagging %s' % case.case_id)
                self._handle_duplicate(case.case_id, close_cases)
            else:
                log('Skipping %s' % case.case_id)

    def _get_case_ids(self):
        with open('case_ids.txt') as f:
            ids = f.readlines()
            return [id.strip() for id in ids]

    def is_duplicate(self, case):
        last_xform_id = case.xform_ids[-1]
        last_xform = FormAccessors(domain=DOMAIN).get_form(last_xform_id)
        return last_xform.xmlns == SYSTEM_FORM_XMLNS and last_xform.received_on < datetime(2018, 4, 2)

    def _handle_duplicate(self, case_id, close_cases):
        if close_cases:
            CaseFactory(DOMAIN).create_or_update_case(
                CaseStructure(
                    case_id=case_id,
                    walk_related=False,
                    attrs={
                        'close': True,
                    },
                )
            )
            log('Closed %s' % case_id)

    @property
    def accessor(self):
        return CaseAccessors(domain=DOMAIN)
