from django.conf import settings
from django.core.management import BaseCommand

from dimagi.utils.couch.cache import cache_core

from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.userreports.reports.filters.values import CHOICE_DELIMITER


class Command(BaseCommand):
    """
        Migrated ReportConfig filters with multiple values from CHOICE_DELIMITER-delimited strings
        to lists. This command can be deleted once that migration is complete.
    """
    def handle(self, *args, **options):
        key = ["name slug"]
        results = cache_core.cached_view(
            ReportConfig.get_db(),
            "reportconfig/configs_by_domain",
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key + [{}]
        )
        count = 0
        for result in results:
            dirty = False
            doc = result['doc']
            config = ReportConfig.get(doc['_id'])
            for name, value in config['filters'].items():
                if isinstance(value, str) and CHOICE_DELIMITER in value:
                    print("Updating config {} filter {}".format(config._id, name))
                    config['filters'][name] = value.split(CHOICE_DELIMITER)
                    dirty = True
            if dirty:
                count = count + 1
                config.save()
        print("Updated {} configs".format(count))
