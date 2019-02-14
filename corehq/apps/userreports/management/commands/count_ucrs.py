from __future__ import absolute_import
from __future__ import print_function

from __future__ import unicode_literals
import textwrap
from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand

from dimagi.utils.couch.database import iter_docs
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class

from corehq.apps.userreports.models import ReportConfiguration, StaticReportConfiguration


class Command(BaseCommand):
    help = "Pull stats about UCR and report-builder reports server-wide"

    def handle(self, **options):
        config_ids = get_doc_ids_by_class(ReportConfiguration)

        builder_count, ucr_count = 0, 0
        for doc in iter_docs(ReportConfiguration.get_db(), config_ids):
            if doc['report_meta']['created_by_builder']:
                builder_count += 1
            else:
                ucr_count += 1

        static_count = len(list(StaticReportConfiguration.all()))
        total_count = builder_count + ucr_count + static_count

        print(textwrap.dedent("""
            As of {}, on {} there are {} total UCRs:
            {} Report Builder Reports
            {} UCR Report Configs
            {} Static Report Configs enabled for the environment
        """.format(datetime.utcnow().date(), settings.SERVER_ENVIRONMENT, total_count,
                   builder_count, ucr_count, static_count)))
