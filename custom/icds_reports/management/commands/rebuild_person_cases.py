from django.core.management.base import BaseCommand
from corehq.apps.userreports.tasks import _get_config_by_id
from corehq.apps.userreports.models import AsyncIndicator
from django.db import connections

from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "Rebuild Person Cases with missing dobs"

    def handle(self, *args, **kwargs):
        # by default execute child cases
        person_config = _get_config_by_id('static-icds-cas-static-person_cases_v3')
        query_june = "SELECT child_person_case_id FROM child_health_monthly WHERE month='2020-06-01' AND dob IS NULL;"
        query_july = "SELECT child_person_case_id FROM child_health_monthly WHERE month='2020-07-01' AND dob IS NULL;"
        ids = set()
        for query in [query_june, query_july]:
            with connections['icds-ucr-citus'].cursor() as cursor:
                cursor.execute(query)
                doc_ids = cursor.fetchall()
                doc_ids = [elem[0] for elem in doc_ids]
                ids.update(set(doc_ids))
        ids = list(ids)
        # removing blank as well None elements from the list and sorting the list
        ids.remove('')
        ids.remove(None)
        ids.sort()
        total_doc_ids = len(ids)
        count = 0
        chunk_size = 1000
        for ids_chunk in chunked(ids, chunk_size):
            ids_list = list(ids_chunk)
            AsyncIndicator.bulk_creation([elem for elem in ids_list], 'CommCareCase', 'icds-cas', [person_config._id])
            count += chunk_size
            print("Success till doc_id: {}".format(ids_list[-1]))
            print("progress: {}/{}".format(count, total_doc_ids))
