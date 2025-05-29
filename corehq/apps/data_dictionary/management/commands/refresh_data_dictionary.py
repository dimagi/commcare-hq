from collections import defaultdict
from django.core.management.base import BaseCommand
from django.http import Http404

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import get_app, get_apps_in_domain
from corehq.apps.app_manager.exceptions import AppInDifferentDomainException
from corehq.apps.data_cleaning.utils.cases import clear_caches_case_data_cleaning
from corehq.apps.domain.models import Domain
from corehq.toggles import VELLUM_SAVE_TO_CASE
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = 'Refreshes data dictionary for all domains and their apps. ' \
           'For specific domains, ./manage.py refresh_data_dictionary domain1 domain2'

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='*',
            help="Domain name(s). If blank, will refresh for all domains")

    def handle(self, **options):
        domains = options['domains'] or Domain.get_all_names()

        for domain in with_progress_bar(domains):
            try:
                apps = get_apps_in_domain(domain)
                for app in apps:
                    try:
                        _refresh_data_dictionary_from_app(domain, app.get_id)
                    except Exception as e:
                        print(f'Failed to refresh app {app.get_id} in domain {domain}: {str(e)}')
                clear_caches_case_data_cleaning(domain)

            except Exception as e:
                print(f'Failed to get apps in domain {domain}: {str(e)}')


def _refresh_data_dictionary_from_app(domain, app_id):
    # This is an exact copy of the function in corehq.apps.app_manager.tasks
    # Except for clear_caches_case_data_cleaning call is deleted
    # The cache will be cleared in the command after all apps are processed
    try:
        app = get_app(domain, app_id)
    except (Http404, AppInDifferentDomainException):
        # If there's no app in the domain, there's nothing to do
        return

    from corehq.apps.app_manager.util import actions_use_usercase
    from corehq.apps.data_dictionary.util import create_properties_for_case_types

    case_type_to_prop = defaultdict(set)
    if VELLUM_SAVE_TO_CASE.enabled(domain):
        for form in app.get_forms():
            case_type_to_prop.update(form.get_save_to_case_updates())
    for module in app.get_modules():
        if not module.is_surveys:
            for form in module.get_forms():
                if form.form_type == 'module_form':
                    case_type_to_prop[module.case_type].update(form.actions.update_case.update)
                    if actions_use_usercase(form.actions):
                        case_type_to_prop[USERCASE_TYPE].update(form.actions.usercase_update.update)
                else:
                    for action in form.actions.load_update_cases:
                        case_type_to_prop[action.case_type].update(action.case_properties)
    if case_type_to_prop:
        create_properties_for_case_types(domain, case_type_to_prop)
