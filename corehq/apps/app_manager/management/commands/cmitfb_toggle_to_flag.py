import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand

from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain

logger = logging.getLogger('cmitfb_toggle_migration')
logger.setLevel('DEBUG')

class Command(BaseCommand):
    help = '''
        Migrate apps to vellum_case_management for domains with
        VELLUM_RICH_TEXT and/or VELLUM_EXPERIMENTAL_UI enabled
    '''

    def handle(self, *args, **options):
        toggle_map = dict([(t.slug, t) for t in all_toggles()])
        domains = [row['key'] for row in Domain.get_all(include_docs=False)]
        for domain in domains:
            if toggle_map['rich_text'].enabled(domain) or toggle_map['experimental_ui'].enabled(domain):
                logger.info('migrating domain {}'.format(domain))
                apps = get_apps_in_domain(domain, include_remote=False)
                for app in apps:
                    call_command('migrate_app_to_cmitfb', app.id)
                toggle_map['rich_text'].set(domain, False, NAMESPACE_DOMAIN)
                toggle_map['experimental_ui'].set(domain, False, NAMESPACE_DOMAIN)
        logger.info('done with cmitfb_toggle_to_flag')
