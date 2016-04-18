from django.core.management.base import BaseCommand

from corehq.apps.reports.dbaccessors import (
    stale_get_exports_json,
    stale_get_export_count,
)
from corehq.apps.export.utils import convert_saved_export_to_export_instance
from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Migrates old exports to new ones"

    def handle(self, *args, **options):

        for doc in Domain.get_all(include_docs=False):
            domain = doc['key']
            export_count = stale_get_export_count(domain)
            if export_count:
                for old_export in with_progress_bar(
                        stale_get_exports_json(domain),
                        length=export_count,
                        prefix=domain):
                    try:
                        convert_saved_export_to_export_instance(domain, old_export)
                    except Exception, e:
                        print 'Failed parsing {}: {}'.format(old_export._id, e)
