from django.core.management.base import LabelCommand, CommandError
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import wrapped_docs


class Command(LabelCommand):
    args = '<domain>'
    help = ('Kill cloudant, by loading a bunch of cases from a single domain.')

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        domain = args[0]
        case_ids = get_case_ids_in_domain(domain)

        print 'loading %s cases in %s' % (len(case_ids), domain)

        def stream_cases(all_case_ids):
            for case_ids in chunked(all_case_ids, 1000):
                for case in wrapped_docs(CommCareCase, keys=case_ids):
                # for case in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True):
                    yield case

        count = 0
        for c in stream_cases(case_ids):
            count += 1
        print 'read %s cases' % count

