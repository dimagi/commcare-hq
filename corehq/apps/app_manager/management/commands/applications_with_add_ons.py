from __future__ import absolute_import, print_function
import csv

from django.core.management.base import BaseCommand
from corehq import toggles
from corehq.apps.app_manager.models import Domain


class Command(BaseCommand):
    help = """
    Checks if an add on is enabled or was ever enabled for applications under all domains
    or under a specific domain with domain name if passed
    Also checks if toggle ENABLE_ALL_ADD_ONS enabled for domains
    """

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str)
        parser.add_argument('add_on_name')

    @staticmethod
    def _iter_domains(options):
        if options.get('domain'):
            yield Domain.get_by_name(options['domain'])
        else:
            domain_ids = [
                result['id'] for result in
                Domain.get_db().view(
                    "domain/domains", reduce=False, include_docs=False
                ).all()
            ]
            print("Count of domains : %s" % len(domain_ids))
            for domain_id in domain_ids:
                yield Domain.get(domain_id)

    def handle(self, add_on_name, *args, **options):
        with open("apps_with_feature_%s.csv" % add_on_name, "w") as csvfile:
            writer = csv.DictWriter(csvfile,
                                    fieldnames=[
                                        'domain', 'application_id', 'app_name',
                                        'all_add_ons_enabled', 'status'
                                    ])
            writer.writeheader()
            for domain in self._iter_domains(options):
                for application in domain.full_applications(include_builds=False):
                    if not application.is_remote_app():
                        all_add_ons_enabled = toggles.ENABLE_ALL_ADD_ONS.enabled(domain.name)
                        if add_on_name in application.add_ons or all_add_ons_enabled:
                            writer.writerow({
                                'domain': domain.name,
                                'application_id': application.get_id,
                                'app_name': application.name,
                                'all_add_ons_enabled': all_add_ons_enabled,
                                'status': application.add_ons.get(add_on_name)
                            })
