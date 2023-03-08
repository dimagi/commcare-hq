from collections import namedtuple
from datetime import datetime

from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids
from corehq.toggles import SYNC_SEARCH_CASE_CLAIM
from corehq.util.log import with_progress_bar

CASE_SEARCH_AUDIT_LOG = "case_search_audit_log.txt"

PropertyInfo = namedtuple("PropertyInfo", "domain app_id version module_unique_id name")


class Command(BaseCommand):
    help = ("Pull all case search options of a given type from all case search apps")

    def add_arguments(self, parser):
        parser.add_argument(
            '-i',
            '--include-builds',
            action='store_true',
            dest='include_builds',
            help='Include saved builds, not just current apps',
        )
        parser.add_argument(
            '-p',
            '--prop-attr',
            action='store_true',
            dest='prop_attr',
            help='Look into property attributes, not just search_config',
        )
        parser.add_argument(
            '-d',
            '--domain',
            action='store',
            help='Audit a single domain',
        )
        parser.add_argument(
            'attr',
            type=str,
            help='Which config option or attribute to find',
        )

    def handle(self, **options):
        include_builds = options['include_builds']
        attr = options['attr']
        if options['domain']:
            domains = [options['domain']]
        else:
            domains = sorted(SYNC_SEARCH_CASE_CLAIM.get_enabled_domains())

        results = []
        for chunk in chunked(with_progress_bar(domains, length=len(domains)), 50):
            for domain in chunk:
                app_ids = get_all_app_ids(domain, include_builds=include_builds)
                for app_id in app_ids:
                    doc = Application.get_db().get(app_id)
                    for index, module in enumerate(doc.get("modules", [])):
                        if module.get("search_config", {}):
                            if options['prop_attr']:
                                for info in self._handle_property_attribute(domain, app_id, doc, module, attr):
                                    results.append(info)
                            elif module.get("search_config").get(attr, None):
                                results.append(PropertyInfo(domain,
                                                            doc.get("copy_of") or app_id,
                                                            doc.get("version"),
                                                            module.get("unique_id"),
                                                            attr))

        result_domains = {r.domain for r in results}
        result_apps = {r.app_id for r in results}
        summary = (f"\n{datetime.now()}\n"
                   f"Found {len(results)} '{attr}' properties"
                   f" in {len(result_apps)} apps"
                   f" in {len(result_domains)} domains\n")

        with open(CASE_SEARCH_AUDIT_LOG, 'a') as f:
            f.write(summary)
        for result in results:
            self.log(result)
        print(summary)

    def _handle_property_attribute(self, domain, app_id, doc, module, attr):
        for prop in module.get("search_config", {}).get("properties", []):
            if prop.get(attr, False):
                yield PropertyInfo(domain,
                                   doc.get("copy_of") or app_id,
                                   doc.get("version"),
                                   module.get("unique_id"),
                                   prop.get("name"))

    def log(self, result):
        with open(CASE_SEARCH_AUDIT_LOG, 'a') as f:
            f.write(f"{str(result)}\n")
