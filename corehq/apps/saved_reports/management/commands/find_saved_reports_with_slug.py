from __future__ import absolute_import, print_function

from __future__ import unicode_literals
from django.conf import settings
from dimagi.utils.couch.cache import cache_core
from corehq.apps.saved_reports.models import ReportConfig

from django.core.management import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('report_slug')

    def handle(self, report_slug, *args, **options):
        kwargs = {'stale': settings.COUCH_STALE_QUERY}
        key = ["name slug"]
        result = cache_core.cached_view(
            ReportConfig.get_db(),
            "reportconfig/configs_by_domain",
            reduce=False, include_docs=False,
            startkey=key, endkey=key + [{}],
            **kwargs)
        for report_config in result:
            domain, owner_id, slug = report_config['key'][1:4]
            if slug == report_slug:
                print("%s, %s, %s" % (
                    domain, owner_id, slug
                ))
