"""
A utility for deleting cases created by the import_drtb_cases management command.
Output is the list of case ids deleted

Example usage:

    > ./manage.py delete_imported_drtb_cases 2017-08-02_093000
    9124ea5b5a83c005532d11e463680b3f
    463680b3f9124ea5b5a83c005532d11e
    1e46363c005532d180b3f9124ea5b5a8
    ...
"""
from __future__ import absolute_import
from __future__ import print_function
from corehq.apps.es import CaseSearchES
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dimagi.utils.chunked import chunked
from django.core.management import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'migration_id',
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually delete the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, migration_id, **options):

        query = CaseSearchES()\
            .domain(domain)\
            .case_property_query("created_by_migration", migration_id, "must", fuzzy=False)
        hits = query.run().hits
        case_ids = [hit['_id'] for hit in hits]

        for case_id in case_ids:
            print(case_id)

        if options['commit']:
            print("Deleting cases")
            for ids in chunked(case_ids, 100):
                CaseAccessors(domain).soft_delete_cases(list(ids))
            print("Deletion finished")
