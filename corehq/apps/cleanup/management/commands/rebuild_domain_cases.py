import logging
from django.core.management.base import BaseCommand, CommandError
from casexml.apps.case.cleanup import rebuild_case
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain


class Command(BaseCommand):
    args = '<domain>'
    help = ('Reprocesses all cases in a domain.')

    def handle(self, *args, **options):
        if len(args) == 1:
            domain = args[0]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        ids = get_case_ids_in_domain(domain)
        for count, case_id in enumerate(ids):
            try:
                rebuild_case(case_id)
                if count % 100 == 0:
                    print 'rebuilt %s/%s cases' % (count, len(ids))
            except Exception, e:
                logging.exception("couldn't rebuild case {id}. {msg}".format(id=case_id, msg=str(e)))
