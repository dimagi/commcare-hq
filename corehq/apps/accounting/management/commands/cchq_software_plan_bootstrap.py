# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Standard library imports
import logging
from optparse import make_option

# Django imports
from django.apps import apps as default_apps
from django.core.management.base import BaseCommand

from corehq.apps.accounting.bootstrap.config.cchq_software_plan_bootstrap import (
    BOOTSTRAP_EDITION_TO_ROLE,
    BOOTSTRAP_FEATURE_RATES,
    BOOTSTRAP_FEATURE_RATES_FOR_TESTING,
    BOOTSTRAP_PRODUCT_RATES,
    FEATURE_TYPES,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate a fresh db with standard set of Software Plans.'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true', default=False,
                    help='Do not actually modify the database, just verbosely log what happen'),
        make_option('--verbose', action='store_true', default=False,
                    help='Enable debug output'),
        make_option('--testing', action='store_true', default=False,
                    help='Run this command for testing purposes.'),
    )

    def handle(self, dry_run=False, verbose=False, testing=False, *args, **options):
        logger.info('Bootstrapping standard plans. Custom plans will have to be created via the admin UIs.')

        if testing:
            logger.info("Initializing Plans and Roles for Testing")
            edition_to_feature_rate = BOOTSTRAP_FEATURE_RATES_FOR_TESTING
        else:
            edition_to_feature_rate = BOOTSTRAP_FEATURE_RATES

        ensure_plans(
            edition_to_role=BOOTSTRAP_EDITION_TO_ROLE,
            edition_to_product_rate=BOOTSTRAP_PRODUCT_RATES,
            edition_to_feature_rate=edition_to_feature_rate,
            feature_types=FEATURE_TYPES,
            dry_run=dry_run, verbose=verbose, apps=default_apps,
        )
