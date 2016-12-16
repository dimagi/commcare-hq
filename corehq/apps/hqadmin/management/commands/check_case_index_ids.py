import csv
from django.core.management import BaseCommand
from corehq.apps.users.util import cached_owner_id_to_display
from corehq.elastic import ES_MAX_CLAUSE_COUNT
from corehq.apps.es.cases import CaseES


class Command(BaseCommand):
    help = "Checks a domain's cases to see if they reference non existing cases"

    def add_arguments(self, parser):
        parser.add_argument('domain', nargs='+')
        parser.add_argument('--filename', dest='filename', default='badcaserefs.csv')

    def handle(self, *args, **options):
        domain = options['domain']
        domain_query = CaseES().domain(domain)
        valid_case_ids = set(domain_query.get_ids())
        referenced_case_ids = {
            index['referenced_id']
            for hit in domain_query.source('indices.referenced_id').run().hits
            for index in hit['indices']
        }

        invalid_referenced_ids = referenced_case_ids - valid_case_ids

        if len(invalid_referenced_ids) > ES_MAX_CLAUSE_COUNT:
            print "there's a lot of invalid ids here. ES queries may not handle this well"

        cases_with_invalid_references = (
            domain_query
            .term('indices.referenced_id', invalid_referenced_ids)
            .source(['_id', 'type', 'indices', 'owner_id', 'opened_by'])
            .run().hits
        )

        with open(options['filename'], 'w') as csvfile:
            writer = csv.writer(csvfile)

            for case in cases_with_invalid_references:
                for index in case['indices']:
                    if index['referenced_id'] in invalid_referenced_ids:
                        writer.writerow([
                            case['_id'],
                            case['type'],
                            index,
                            case['owner_id'],
                            cached_owner_id_to_display(case['owner_id']),
                            case['opened_by'],
                            cached_owner_id_to_display(case['opened_by']),
                        ])
