# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Standard library imports
from collections import defaultdict
from decimal import Decimal
import logging
from optparse import make_option

# Django imports
from django.apps import apps as default_apps
from django.core.management.base import BaseCommand

from corehq.apps.accounting.exceptions import AccountingError
from corehq.apps.accounting.models import (
    SoftwareProductType, SoftwarePlanEdition, SoftwarePlanVisibility, FeatureType,
    UNLIMITED_FEATURE_USAGE,
)


logger = logging.getLogger(__name__)

BOOTSTRAP_EDITION_TO_ROLE = {
    SoftwarePlanEdition.COMMUNITY: 'community_plan_v0',
    SoftwarePlanEdition.STANDARD: 'standard_plan_v0',
    SoftwarePlanEdition.PRO: 'pro_plan_v0',
    SoftwarePlanEdition.ADVANCED: 'advanced_plan_v0',
    SoftwarePlanEdition.ENTERPRISE: 'enterprise_plan_v0',
}
EDITIONS = [
    SoftwarePlanEdition.COMMUNITY,
    SoftwarePlanEdition.STANDARD,
    SoftwarePlanEdition.PRO,
    SoftwarePlanEdition.ADVANCED,
    SoftwarePlanEdition.ENTERPRISE,
]
FEATURE_TYPES = [f[0] for f in FeatureType.CHOICES]
PRODUCT_TYPES = [p[0] for p in SoftwareProductType.CHOICES]


class Command(BaseCommand):
    help = 'Populate a fresh db with standard set of Software Plans.'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help='Do not actually modify the database, just verbosely log what happen'),
        make_option('--verbose', action='store_true',  default=False,
                    help='Enable debug output'),
        make_option('--testing', action='store_true',  default=False,
                    help='Run this command for testing purposes.'),
    )

    def handle(self, dry_run=False, verbose=False, testing=False, *args, **options):
        logger.info('Bootstrapping standard plans. Enterprise plans will have to be created via the admin UIs.')

        for_tests = testing
        if for_tests:
            logger.info("Initializing Plans and Roles for Testing")

        ensure_plans(dry_run=dry_run, verbose=verbose, for_tests=for_tests, apps=default_apps)


def ensure_plans(dry_run, verbose, for_tests, apps):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    SoftwarePlan = apps.get_model('accounting', 'SoftwarePlan')
    SoftwarePlanVersion = apps.get_model('accounting', 'SoftwarePlanVersion')
    Role = apps.get_model('django_prbac', 'Role')

    edition_to_features = _ensure_features(dry_run=dry_run, verbose=verbose, apps=apps)
    for product_type in PRODUCT_TYPES:
        for edition in EDITIONS:
            role_slug = BOOTSTRAP_EDITION_TO_ROLE[edition]
            try:
                role = Role.objects.get(slug=role_slug)
            except Role.DoesNotExist:
                logger.info("Could not find the role '%s'. Did you forget to run cchq_prbac_bootstrap?")
                logger.info("Aborting. You should figure this out.")
                return
            software_plan_version = SoftwarePlanVersion(role=role)

            product, product_rates = _ensure_product_and_rate(product_type, edition, dry_run=dry_run, verbose=verbose, apps=apps)
            feature_rates = _ensure_feature_rates(edition_to_features[edition], edition, dry_run=dry_run, verbose=verbose, for_tests=for_tests, apps=apps)
            software_plan = SoftwarePlan(
                name='%s Edition' % product.name, edition=edition, visibility=SoftwarePlanVisibility.PUBLIC
            )
            if dry_run:
                logger.info("[DRY RUN] Creating Software Plan: %s" % software_plan.name)
            else:
                try:
                    software_plan = SoftwarePlan.objects.get(name=software_plan.name)
                    if verbose:
                        logger.info("Plan '%s' already exists. Using existing plan to add version."
                                    % software_plan.name)
                except SoftwarePlan.DoesNotExist:
                    software_plan.save()
                    if verbose:
                        logger.info("Creating Software Plan: %s" % software_plan.name)

                    software_plan_version.plan = software_plan

                    # must save before assigning many-to-many relationship
                    if hasattr(SoftwarePlanVersion, 'product_rates'):
                        software_plan_version.save()

                    for product_rate in product_rates:
                        product_rate.save()
                        if hasattr(SoftwarePlanVersion, 'product_rates'):
                            software_plan_version.product_rates.add(product_rate)
                        elif hasattr(SoftwarePlanVersion, 'product_rate'):
                            assert len(product_rates) == 1
                            software_plan_version.product_rate = product_rate
                        else:
                            raise AccountingError('SoftwarePlanVersion does not have product_rate or product_rates field')

                    # must save before assigning many-to-many relationship
                    if hasattr(SoftwarePlanVersion, 'product_rate'):
                        software_plan_version.save()

                    for feature_rate in feature_rates:
                        feature_rate.save()
                        software_plan_version.feature_rates.add(feature_rate)
                    software_plan_version.save()

            if edition == SoftwarePlanEdition.ADVANCED:
                trials = [True, False]
            else:
                trials = [False]
            for is_trial in trials:
                default_product_plan = DefaultProductPlan(product_type=product.product_type, edition=edition, is_trial=is_trial)
                if dry_run:
                    logger.info("[DRY RUN] Setting plan as default for product '%s' and edition '%s'." %
                            (product.product_type, default_product_plan.edition))
                else:
                    try:
                        default_product_plan = DefaultProductPlan.objects.get(product_type=product.product_type,
                                                                              edition=edition, is_trial=is_trial)
                        if verbose:
                            logger.info("Default for product '%s' and edition "
                                        "'%s' already exists." % (
                                            product.product_type, default_product_plan.edition
                                        ))
                    except DefaultProductPlan.DoesNotExist:
                        default_product_plan.plan = software_plan
                        default_product_plan.save()
                        if verbose:
                            logger.info("Setting plan as default for product '%s' and edition '%s'." %
                                        (product.product_type,
                                         default_product_plan.edition))


def _ensure_product_and_rate(product_type, edition, dry_run, verbose, apps):
    """
    Ensures that all the necessary SoftwareProducts and SoftwareProductRates are created for the plan.
    """
    SoftwareProduct = apps.get_model('accounting', 'SoftwareProduct')
    SoftwareProductRate = apps.get_model('accounting', 'SoftwareProductRate')

    if verbose:
        logger.info('Ensuring Products and Product Rates')

    product = SoftwareProduct(name='%s %s' % (product_type, edition), product_type=product_type)
    if edition == SoftwarePlanEdition.ENTERPRISE:
        product.name = "Dimagi Only %s" % product.name

    product_rates = []
    BOOTSTRAP_PRODUCT_RATES = {
        SoftwarePlanEdition.COMMUNITY: [
            SoftwareProductRate(),  # use all the defaults
        ],
        SoftwarePlanEdition.STANDARD: [
            SoftwareProductRate(monthly_fee=Decimal('100.00')),
        ],
        SoftwarePlanEdition.PRO: [
            SoftwareProductRate(monthly_fee=Decimal('500.00')),
        ],
        SoftwarePlanEdition.ADVANCED: [
            SoftwareProductRate(monthly_fee=Decimal('1000.00')),
        ],
        SoftwarePlanEdition.ENTERPRISE: [
            SoftwareProductRate(monthly_fee=Decimal('0.00')),
        ],
    }

    for product_rate in BOOTSTRAP_PRODUCT_RATES[edition]:
        if dry_run:
            logger.info("[DRY RUN] Creating Product: %s" % product)
            logger.info("[DRY RUN] Corresponding product rate of $%d created." % product_rate.monthly_fee)
        else:
            try:
                product = SoftwareProduct.objects.get(name=product.name)
                if verbose:
                    logger.info("Product '%s' already exists. Using "
                                "existing product to add rate."
                                % product.name)
            except SoftwareProduct.DoesNotExist:
                product.save()
                if verbose:
                    logger.info("Creating Product: %s" % product)
            if verbose:
                logger.info("Corresponding product rate of $%d created."
                            % product_rate.monthly_fee)
        product_rate.product = product
        product_rates.append(product_rate)
    return product, product_rates


def _ensure_features(dry_run, verbose, apps):
    """
    Ensures that all the Features necessary for the plans are created.
    """
    Feature = apps.get_model('accounting', 'Feature')

    if verbose:
        logger.info('Ensuring Features')

    edition_to_features = defaultdict(list)
    for edition in EDITIONS:
        for feature_type in FEATURE_TYPES:
            feature = Feature(name='%s %s' % (feature_type, edition), feature_type=feature_type)
            if edition == SoftwarePlanEdition.ENTERPRISE:
                feature.name = "Dimagi Only %s" % feature.name
            if dry_run:
                logger.info("[DRY RUN] Creating Feature: %s" % feature)
            else:
                try:
                    feature = Feature.objects.get(name=feature.name)
                    if verbose:
                        logger.info("Feature '%s' already exists. Using "
                                    "existing feature to add rate."
                                    % feature.name)
                except Feature.DoesNotExist:
                    feature.save()
                    if verbose:
                        logger.info("Creating Feature: %s" % feature)
            edition_to_features[edition].append(feature)
    return edition_to_features


def _ensure_feature_rates(features, edition, dry_run, verbose, for_tests, apps):
    """
    Ensures that all the FeatureRates necessary for the plans are created.
    """
    FeatureRate = apps.get_model('accounting', 'FeatureRate')

    if verbose:
        logger.info('Ensuring Feature Rates')

    feature_rates = []
    BOOTSTRAP_FEATURE_RATES = {
        SoftwarePlanEdition.COMMUNITY: {
            FeatureType.USER: FeatureRate(monthly_limit=2 if for_tests else 50,
                                          per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=0),  # use defaults here
        },
        SoftwarePlanEdition.STANDARD: {
            FeatureType.USER: FeatureRate(monthly_limit=4 if for_tests else 100,
                                          per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=3 if for_tests else 100),
        },
        SoftwarePlanEdition.PRO: {
            FeatureType.USER: FeatureRate(monthly_limit=6 if for_tests else 500,
                                          per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=5 if for_tests else 500),
        },
        SoftwarePlanEdition.ADVANCED: {
            FeatureType.USER: FeatureRate(monthly_limit=8 if for_tests else 1000,
                                          per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=7 if for_tests else 1000),
        },
        SoftwarePlanEdition.ENTERPRISE: {
            FeatureType.USER: FeatureRate(monthly_limit=UNLIMITED_FEATURE_USAGE, per_excess_fee=Decimal('0.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=UNLIMITED_FEATURE_USAGE),
        },
    }
    for feature in features:
        feature_rate = BOOTSTRAP_FEATURE_RATES[edition][feature.feature_type]
        feature_rate.feature = feature
        if dry_run:
            logger.info("[DRY RUN] Creating rate for feature '%s': %s" % (feature.name, feature_rate))
        elif verbose:
            logger.info("Creating rate for feature '%s': %s" % (feature.name, feature_rate))
        feature_rates.append(feature_rate)
    return feature_rates
