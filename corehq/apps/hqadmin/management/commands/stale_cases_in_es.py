
import inspect

from django.core.management.base import BaseCommand
from datetime import datetime
from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.apps.es import CaseES
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.util.dates import iso_string_to_datetime
from corehq.util.couch_helpers import paginate_view


class Command(BaseCommand):
    """
    Returns list of couch case_ids that are not updated in ES

        $ ./manage.py stale_cases_in_es <DOMAIN> > case_ids.txt

    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        for case_id in get_server_modified_on_for_domain(domain):
            print(case_id)


def get_server_modified_on_for_domain(domain):
    start_time = datetime.utcnow()
    chunk_size = 1000
    chunked_iterator = chunked(paginate_view(
        CommCareCase.get_db(),
        'cases_by_server_date/by_server_modified_on',
        chunk_size=chunk_size,
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=False
    ), chunk_size)
    for chunk in chunked_iterator:
        case_ids = [row['id'] for row in chunk]
        results = (CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on'))
        es_modified_on_by_ids = {_id: modified_on for _id, modified_on in results }
        for row in chunk:
            case_id, couch_modified_on = row['id'], row['value']
            if iso_string_to_datetime(couch_modified_on) > start_time:
                # skip cases modified after the script started
                continue
            es_modified_on = es_modified_on_by_ids.get(case_id)
            if not es_modified_on or (es_modified_on != couch_modified_on):
                yield (case_id, es_modified_on, couch_modified_on)
