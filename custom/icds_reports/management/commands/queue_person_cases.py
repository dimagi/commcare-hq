
from django.core.management.base import BaseCommand
from corehq.apps.userreports.tasks import _get_config_by_id
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.models import AsyncIndicator
from django.db import connections, models, transaction, router


class Command(BaseCommand):
    help = "Rebuild Bihar person cases "

    def handle(self):
        person_config = _get_config_by_id('static-icds-cas-static-person_cases_v3')
        table_name = get_table_name('icds-cas', 'static-person_cases_v3')
        query = """select doc_id from "{}" where state_id='f9b47ea2ee2d8a02acddeeb491d3e175'""".format(table_name)

        with connections['icds-ucr-citus'].cursor()  as cursor:
            cursor.execute(query)
            doc_ids = cursor.fetchall()
            doc_ids = [doc[0] for doc in doc_ids]

        for doc_id in doc_ids:
            AsyncIndicator.update_record(
                doc_id, person_config.referenced_doc_type, person_config.domain, [person_config._id]
            )
