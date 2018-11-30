"""
Find and optionally fix child cases that have been created without a
parent index.

NOTE: This script does not inspect the cases. It will return fixed
cases. It will also return parent cases, which don't need to be fixed.

Generate a list of cases (both parent and child cases) and dump it to a
CSV file:

    $ ./manage.py find_child_noindex > cases.csv
    ....

Read the cases from a CSV file, and rebuild them:

    $ ./manage.py find_child_noindex --fix --caselist cases.csv

Or do both in the same step:

    $ ./manage.py find_child_noindex --fix
    ....

"""
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import csv
import sys

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.domain.models import Domain
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import RebuildWithReason
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.quickcache import quickcache


def read_caselist(caselist_filename):
    with open(caselist_filename) as case_list:
        csv_reader = csv.reader(case_list)
        for domain, case_id in csv_reader:
            yield domain, case_id


def find_domain_case_ids():
    domains = [row['key'] for row in Domain.get_all(include_docs=False)]
    for domain in domains:
        sys.stderr.write('.')  # Use STDERR so we can redirect STDOUT without dots
        case_accessors = CaseAccessors(domain)
        for app in get_apps_in_domain(domain, include_remote=False):
            for module in app.get_modules():
                case_type = module.case_type
                subcase_types = module.get_subcase_types()
                if case_type in subcase_types:
                    for case_id in case_accessors.iter_case_ids_by_domain_and_type(case_type):
                        yield domain, case_id
        sys.stderr.write('\n')


@quickcache(['domain'])
def get_form_processor(domain):
    if should_use_sql_backend(domain):
        return FormProcessorSQL
    else:
        return FormProcessorCouch


def rebuild_case(domain, case_id):
    form_processor = get_form_processor(domain)
    detail = RebuildWithReason(reason='Create possible child case with parent index')
    form_processor.hard_rebuild_case(domain, case_id, detail)


class Command(BaseCommand):
    help = 'Find child cases that have been created without a parent index'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--fix', action='store_true')
        parser.add_argument('-l', '--caselist', metavar='CSV_FILE')

    def handle(self, fix, caselist, **options):
        if caselist:
            domain_case_ids = read_caselist(caselist)
        else:
            domain_case_ids = find_domain_case_ids()
        csv_writer = csv.writer(sys.stdout)
        for domain, case_id in domain_case_ids:
            csv_writer.writerow((domain, case_id))
            if fix:
                rebuild_case(domain, case_id)
