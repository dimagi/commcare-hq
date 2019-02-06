from __future__ import absolute_import
from __future__ import print_function

import textwrap
from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand

from dimagi.utils.couch.database import iter_docs
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.log import with_progress_bar

from corehq.apps.userreports.models import ReportConfiguration


class Command(BaseCommand):
    help = "Pull stats about UCR and report-builder reports server-wide"

    def handle(self, **options):
        config_ids = get_doc_ids_by_class(ReportConfiguration)
        total_count = len(config_ids)

        builder_count, ucr_count = 0, 0
        for doc in with_progress_bar(iter_docs(ReportConfiguration.get_db(), config_ids), total_count):
            if doc['report_meta']['created_by_builder']:
                builder_count += 1
            else:
                ucr_count += 1

        print(textwrap.dedent("""
            As of {}, on {} there are {} total UCRs:
            {} Report Builder Reports
            {} UCR Report Configs
        """.format(datetime.utcnow().date(), settings.SERVER_ENVIRONMENT, total_count,
                   builder_count, ucr_count)))
