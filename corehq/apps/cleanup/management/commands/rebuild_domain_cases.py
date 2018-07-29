from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from django.core.management.base import BaseCommand, CommandError
from casexml.apps.case.cleanup import rebuild_case_from_forms
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.form_processor.models import RebuildWithReason
from corehq.form_processor.utils import should_use_sql_backend


class Command(BaseCommand):
    help = ('Reprocesses all cases in a domain. Only works with couch-based domains')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('reason')

    def handle(self, domain, reason, **options):
        if should_use_sql_backend(domain):
            raise CommandError('This command only works for couch-based domains.')

        ids = get_case_ids_in_domain(domain)
        for count, case_id in enumerate(ids):
            try:
                rebuild_case_from_forms(domain, case_id, RebuildWithReason(reason=reason))
                if count % 100 == 0:
                    print('rebuilt %s/%s cases' % (count, len(ids)))
            except Exception as e:
                logging.exception("couldn't rebuild case {id}. {msg}".format(id=case_id, msg=str(e)))
