from __future__ import print_function
from __future__ import absolute_import
import cProfile
import pstats

from django.core.management.base import BaseCommand

from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.models import get_datasource_config


class Command(BaseCommand):
    help = "Profile a data source's processing time"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('data_source_id')
        parser.add_argument('doc_id')

    def handle(self, domain, data_source_id, doc_id, **options):
        config, _ = get_datasource_config(data_source_id, domain)
        doc_type = config.referenced_doc_type
        doc_store = get_document_store(domain, doc_type)
        doc = doc_store.get_document(doc_id)

        local_variables = {'config': config, 'doc': doc}

        cProfile.runctx('config.get_all_values(doc)', {}, local_variables, 'ucr_stats.log')
        p = pstats.Stats('ucr_stats.log')
        p.sort_stats('cumulative')

        print("Top 10 functions by cumulative time\n")
        p.print_stats(10)

        print("Specs timing\n")
        p.print_stats('userreports.*specs.*\(__call__\)')

        print("Socket recvs\n")
        p.print_stats('recv')

        print("Doc retrievals\n")
        p.print_stats('document_store.*\(get_document\)')

        print("Postgres queries\n")
        p.print_stats('execute.*psycopg')

        print("ES queries\n")
        p.print_stats('es_query.py.*\(run\)')

        print("""
        Note: Due to overhead in profiling, these times are much larger than the real times.

        Next Steps:
           1) choose one of the previous calls to investigate
           2) use print_callees or print_callers to follow the calls
              * usage https://docs.python.org/2/library/profile.html#pstats.Stats.print_stats
           3) check out branch je/time-ucr to get logs for processing time of each column
              (you'll likely need to rebase it on latest master)
        """)
