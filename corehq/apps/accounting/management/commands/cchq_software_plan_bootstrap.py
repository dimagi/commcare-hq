# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Django imports
from django.apps import apps as default_apps
from django.core.management.base import BaseCommand

from corehq.apps.accounting.bootstrap.config.cchq_software_plan_bootstrap import (
    BOOTSTRAP_CONFIG, BOOTSTRAP_CONFIG_TESTING
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.apps.accounting.utils import log_accounting_info


class Command(BaseCommand):
    help = 'Populate a fresh db with standard set of Software Plans.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Enable debug output',
        )
        parser.add_argument(
            '--testing',
            action='store_true',
            default=False,
            help='Run this command for testing purposes.',
        )

    def handle(self, verbose=False, testing=False, *args, **options):
        log_accounting_info(
            'Bootstrapping standard plans. Custom plans will have to be created via the admin UIs.'
        )

        if testing:
            log_accounting_info("Initializing Plans and Roles for Testing")
            config = BOOTSTRAP_CONFIG_TESTING
        else:
            config = BOOTSTRAP_CONFIG

        ensure_plans(config, verbose=verbose, apps=default_apps)
