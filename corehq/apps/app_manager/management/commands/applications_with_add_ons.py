# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
from __future__ import unicode_literals
import csv342 as csv

from django.core.management.base import BaseCommand, CommandError
from corehq import toggles
from corehq.apps.app_manager.models import Domain
from corehq.apps.toggle_ui.utils import find_static_toggle
from corehq.toggles import NAMESPACE_DOMAIN
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.app_manager.models import Application
from io import open


class Command(BaseCommand):
    help = """
    Checks if an add on is enabled or was ever enabled for applications under all domains
    or under a specific domain with domain name if passed
    Also checks if toggle ENABLE_ALL_ADD_ONS enabled for domains
    Can also enable the domains found for another toggle in case the add-on is meant to
    be switched to a toggle
    Example: ./manage.py applications_with_add_ons custom_icon_badges
             --add_to_toggle=new_custom_icon
    """

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str)
        parser.add_argument('add_on_name')
        parser.add_argument('--add_to_toggle')

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
        add_to_toggle = options.get('add_to_toggle')
        if add_to_toggle:
            add_to_toggle = find_static_toggle(add_to_toggle)
            if not add_to_toggle:
                raise CommandError('Toggle %s not found.' % add_to_toggle)
        with open("apps_with_feature_%s.csv" % add_on_name, "w", encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile,
                                    fieldnames=[
                                        'domain', 'application_id', 'app_name',
                                        'all_add_ons_enabled', 'status'
                                    ])
            writer.writeheader()
            for domain_obj in self._iter_domains(options):
                application_ids = get_app_ids_in_domain(domain_obj.name)
                for application_id in application_ids:
                    application = Application.get(application_id)
                    if not application.is_remote_app():
                        all_add_ons_enabled = toggles.ENABLE_ALL_ADD_ONS.enabled(domain_obj.name)
                        if add_on_name in application.add_ons or all_add_ons_enabled:
                            try:
                                writer.writerow({
                                    'domain': domain_obj.name.encode('utf-8'),
                                    'application_id': application.get_id,
                                    'app_name': application.name.encode('utf-8'),
                                    'all_add_ons_enabled': all_add_ons_enabled,
                                    'status': application.add_ons.get(add_on_name)
                                })
                                if add_to_toggle:
                                    add_to_toggle.set(domain_obj.name, True, NAMESPACE_DOMAIN)
                            except UnicodeEncodeError:
                                print('encode error')
                                print({
                                    'domain': domain_obj.name,
                                    'application_id': application.get_id,
                                    'app_name': application.name,
                                    'all_add_ons_enabled': all_add_ons_enabled,
                                    'status': application.add_ons.get(add_on_name)
                                })
