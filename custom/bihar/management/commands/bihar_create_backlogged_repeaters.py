from datetime import datetime
import logging
from django.core.management.base import BaseCommand
from corehq.apps.hqcase.dbaccessors import get_cases_in_domain
from corehq.apps.receiverwrapper.models import CaseRepeater


class Command(BaseCommand):
    """
    Creates the backlog of repeat records that were dropped when bihar repeater
    infrastructure went down.
    """

    def handle(self, *args, **options):
        domain = 'care-bihar'

        # forward all cases that were last modified between these dates
        def should_forward_case(case):
            min_date = datetime(2013, 9, 10)
            max_date = datetime(2013, 11, 7)
            return (case.server_modified_on
                    and min_date < case.server_modified_on < max_date)

        prod_repeater = CaseRepeater.get('a478a5a3d8964338cb3124de77e3ec58')
        success_count = 0
        fail_count = 0
        for case in get_cases_in_domain(domain):
            try:
                if should_forward_case(case):
                    prod_repeater.register(case)
                    success_count += 1
            except Exception:
                fail_count += 1
                logging.exception('problem creating repeater stub for case %s' % case._id)

        print 'successfully forwarded %s cases. %s were not processed' % (success_count, fail_count)
