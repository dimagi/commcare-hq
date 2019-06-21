from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand

from corehq import privileges
from corehq.apps.accounting.models import DefaultProductPlan
from corehq.apps.accounting.subscription_changes import DomainDowngradeStatusHandler
from corehq.apps.app_manager.dbaccessors import get_all_apps
from corehq.apps.app_manager.util import app_callout_templates
from corehq.apps.domain.models import Domain
from six.moves import map


class Command(BaseCommand):
    help = 'Print out a CSV containing a table of what features are in use by project space.'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_names',
            metavar='domain',
            nargs='+',
        )

    def handle(self, domain_names, **kwargs):
        privileges = sorted(_privilege_to_response_function().keys())
        print(','.join(['Project Space'] + privileges + ['Lowest Plan']))
        for domain_obj in [d for d in map(Domain.get_by_name, domain_names) if d]:
            is_privilege_being_used = {
                priv: _is_domain_using_privilege(domain_obj, priv)
                for priv in privileges
            }
            using_privileges = [priv for (priv, is_in_use) in is_privilege_being_used.items() if is_in_use]
            minimum_plan = DefaultProductPlan.get_lowest_edition(using_privileges)
            print(','.join(
                [domain_obj.name] +
                ['X' if is_privilege_being_used[priv] else '' for priv in privileges] +
                [minimum_plan]
            ))


def _privilege_to_response_function():
    privilege_to_response_function = DomainDowngradeStatusHandler.privilege_to_response_function()
    privilege_to_response_function.update({
        privileges.CUSTOM_REPORTS: _domain_has_custom_report,
        privileges.LOCATIONS: _domain_uses_locations,
        privileges.TEMPLATED_INTENTS: _domain_has_apps_using_templated_intents,
        privileges.CUSTOM_INTENTS: _domain_has_apps_using_custom_intents,
    })
    return privilege_to_response_function


def _is_domain_using_privilege(domain_obj, privilege):
    if domain_obj.has_privilege(privilege):
        return bool(_privilege_to_response_function()[privilege](domain_obj))
    return False


def _domain_has_custom_report(domain_obj):
    from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
    return bool(CustomProjectReportDispatcher().get_reports(domain_obj.name))


def _domain_uses_locations(domain_obj):
    return domain_obj.uses_locations


# This will take long time
def _domain_has_apps_using_templated_intents(domain_obj):
    templates = next(app_callout_templates)
    template_ids = set([t['id'] for t in templates])
    return any(
        any(
            any(
                intent in template_ids
                for intent in form.wrapped_xform().odk_intents
            )
            for form in app.get_forms()
        )
        for app in get_all_apps(domain_obj.name)
    )


# This will take a long time
def _domain_has_apps_using_custom_intents(domain_obj):
    templates = next(app_callout_templates)
    template_ids = set([t['id'] for t in templates])
    return any(
        any(
            any(set(form.wrapped_xform().odk_intents) - template_ids)
            for form in app.get_forms()
        )
        for app in get_all_apps(domain_obj.name)
    )
