from __future__ import absolute_import, print_function
from __future__ import unicode_literals
from collections import Counter
from django.core.management.base import BaseCommand
from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors


class Command(BaseCommand):
    help = "List forms and cases in a domain by shard ID."

    def add_arguments(self, parser):
        parser.add_argument('domain', help='Domain to create data in.')

    def handle(self, domain, **options):
        forms_by_shard = Counter()
        forms_by_db = Counter()
        cases_by_shard = Counter()
        cases_by_db = Counter()
        print('======================== forms ========================')
        print('id\t\t\t\t\tshard\tdatabase')
        for form_id in sorted(FormAccessors(domain=domain).get_all_form_ids_in_domain()):
            shard_id, dbname = ShardAccessor.get_shard_id_and_database_for_doc(form_id)
            forms_by_shard[shard_id] += 1
            forms_by_db[dbname] += 1
            print('{}\t{}\t{}'.format(form_id, shard_id, dbname))
        print('\n======================== cases ========================')
        print('id\t\t\t\t\tshard\tdatabase')
        for case_id in sorted(CaseAccessors(domain=domain).get_case_ids_in_domain()):
            shard_id, dbname = ShardAccessor.get_shard_id_and_database_for_doc(case_id)
            cases_by_shard[shard_id] += 1
            cases_by_db[dbname] += 1
            print('{}\t{}\t{}'.format(case_id, shard_id, dbname))
        _print(forms_by_shard, 'forms by shard')
        _print(forms_by_db, 'forms by db')
        _print(cases_by_shard, 'cases by shard')
        _print(cases_by_db, 'cases by db')


def _print(counter, name):
    print('\n{}'.format(name))
    for key in sorted(counter):
        print('{}\t{}'.format(key, counter[key]))
