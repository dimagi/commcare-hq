from __future__ import print_function
from optparse import make_option
from django.core.management.base import BaseCommand
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import sessionmaker
from corehq.apps.callcenter.utils import get_call_center_domains, get_or_create_mapping
from ctable.models import SqlExtractMapping
from ctable.util import get_extractor
from django.conf import settings

mapping_name = 'cc_form_submissions'


class Command(BaseCommand):
    help = 'Remove legacy call center data'

    option_list = BaseCommand.option_list + (
        make_option('--all-tables', action='store_true',  default=False,
                    help="Delete all tables regardless of domain setting"),
        make_option('--all-mappings', action='store_true',  default=False,
                    help="Delete all mappings and mappings regardless of domain setting"),
        make_option('--dry-run', action='store_true',  default=False,
                    help="Don't actually do anything"),
    )

    def handle(self, *args, **options):
        drop_all_tables = options.get('all-tables', False)
        delete_all_mappings = options.get('all-mappings', False)
        dry_run = options.get('dry_run', False)

        if dry_run:
            print("\n-------- DRY RUN --------\n")

        all_tables = get_db_tables(settings.SQL_REPORTING_DATABASE_URL)

        domains = get_call_center_domains()
        for domain in domains:
            print("Processing domain", domain)
            mapping = get_or_create_mapping(domain, mapping_name)

            if mapping.table_name in all_tables:
                print("\tDropping SQL table", mapping.table_name)
                if not dry_run:
                    extractor = get_extractor(mapping.backend)
                    extractor.clear_all_data(mapping)

            if not mapping.new_document:
                print("\tDeleting ctable mapping", mapping.name)
                if not dry_run:
                    mapping.delete()

        missed_tables = [t for t in all_tables if t.endswith(mapping_name)]
        if missed_tables:
            print('\nSome tables are still hanging around:')
            with extractor.backend as backend:
                for table in missed_tables:
                    if not drop_all_tables:
                        print('\t*', table)
                    else:
                        print("\tDeleting table", table)
                        backend.op.drop_table(table)

            if not drop_all_tables:
                print("\n To delete these tables run with '--all-tables'")

        all_mappings = SqlExtractMapping.all()
        missed_mappings = [m for m in all_mappings if m.name == mapping_name]
        if missed_mappings:
            print('\nSome mappings are still hanging around:')
            for mapping in missed_mappings:
                if not delete_all_mappings:
                    print('\t*', mapping.name, 'for domains', ', '.join(mapping.domains))
                else:
                    print('\tDeleting mapping', mapping.name, 'for domains', ', '.join(mapping.domains))
                    mapping.delete()

            if not delete_all_mappings:
                print("\n To delete these mappings run with '--all-mappings'")


def get_session(url):
    engine = create_engine(url)
    session = sessionmaker(bind=engine)
    return session()


def get_db_tables(database_url):
    session = get_session(database_url)
    results = session.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public';
        """)

    return [r[0] for r in results]
