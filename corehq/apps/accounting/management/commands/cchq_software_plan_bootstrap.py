# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Standard library imports
from collections import defaultdict
from decimal import Decimal
import logging
from optparse import make_option

# Django imports
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from corehq.apps.accounting.models import SoftwarePlan, SoftwareProductType, SoftwarePlanEdition, SoftwarePlanVisibility, SoftwareProduct, SoftwareProductRate, Feature, FeatureRate, FeatureType, SoftwarePlanVersion, DefaultProductPlan
from django_prbac.models import Role

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate a fresh db with standard set of Software Plans.'

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help='Do not actually modify the database, just verbosely log what happen'),
        make_option('--verbose', action='store_true',  default=False,
                    help='Enable debug output'),
        make_option('--fresh-start', action='store_true',  default=False,
                    help='Wipe all plans and start over. USE CAUTION.'),
        make_option('--flush', action='store_true',  default=False,
                    help='Wipe all plans and start over. USE CAUTION.'),
    )

    def handle(self, dry_run=False, verbose=False, fresh_start=False, flush=False, *args, **options):
        logging.info('Bootstrapping standard plans. Enterprise plans will have to be created via the admin UIs.')

        if verbose:
            logger.setLevel(logging.DEBUG)

        if fresh_start or flush:
            confirm_fresh_start = input("Are you sure you want to delete all SoftwarePlans and start over? "
                                        "You can't do this if there are any active Subscriptions."
                                        " Type 'yes' to continue.")
            if confirm_fresh_start == 'yes':
                self.flush_plans()

        if not flush:
            self.product_types = [p[0] for p in SoftwareProductType.CHOICES]
            self.editions = [
                SoftwarePlanEdition.COMMUNITY,
                SoftwarePlanEdition.STANDARD,
                SoftwarePlanEdition.PRO,
                SoftwarePlanEdition.ADVANCED,
            ]
            self.feature_types = [f[0] for f in FeatureType.CHOICES]
            self.ensure_plans(dry_run=dry_run)

    def flush_plans(self):
        logging.info("Flushing ALL SoftwarePlans...")
        DefaultProductPlan.objects.all().delete()
        SoftwarePlanVersion.objects.all().delete()
        SoftwarePlan.objects.all().delete()
        SoftwareProductRate.objects.all().delete()
        SoftwareProduct.objects.all().delete()
        FeatureRate.objects.all().delete()
        Feature.objects.all().delete()

    def ensure_plans(self, dry_run=False):
        edition_to_features = self.ensure_features(dry_run=dry_run)
        for product_type in self.product_types:
            for edition in self.editions:
                role_slug = self.BOOTSTRAP_EDITION_TO_ROLE[edition]
                try:
                    role = Role.objects.get(slug=role_slug)
                except ObjectDoesNotExist:
                    logging.info("Could not find the role '%s'. Did you forget to run cchq_prbac_bootstrap?")
                    logging.info("Aborting. You should figure this out.")
                    return
                software_plan_version = SoftwarePlanVersion(role=role)

                product, product_rates = self.ensure_product_and_rate(product_type, edition, dry_run=dry_run)
                feature_rates = self.ensure_feature_rates(edition_to_features[edition], edition, dry_run=dry_run)
                software_plan = SoftwarePlan(
                    name='%s Edition' % product.name, edition=edition, visibility=SoftwarePlanVisibility.PUBLIC
                )
                if dry_run:
                    logging.info("[DRY RUN] Creating Software Plan: %s" % software_plan)
                else:
                    try:
                        software_plan = SoftwarePlan.objects.get(name=software_plan.name)
                        logging.info("Plan '%s' already exists. Using existing plan to add version."
                                     % software_plan.name)
                    except ObjectDoesNotExist:
                        software_plan.save()
                        logging.info("Creating Software Plan: %s" % software_plan)

                    software_plan_version.plan = software_plan
                    software_plan_version.save()
                    for product_rate in product_rates:
                        software_plan_version.product_rates.add(product_rate)
                    for feature_rate in feature_rates:
                        software_plan_version.feature_rates.add(feature_rate)
                    software_plan_version.save()

                if edition == SoftwarePlanEdition.COMMUNITY:
                    default_product_plan = DefaultProductPlan(product_type=product.product_type)
                    if dry_run:
                        logging.info("[DRY RUN] Setting plan as default for product '%s'." % product.product_type)
                    else:
                        try:
                            default_product_plan = DefaultProductPlan.objects.get(product_type=product.product_type)
                            logging.info("Default for product '%s' already exists." % product.product_type)
                        except ObjectDoesNotExist:
                            default_product_plan.plan = software_plan
                            default_product_plan.save()
                            logging.info("Setting plan as default for product '%s'." % product.product_type)

    def ensure_product_and_rate(self, product_type, edition, dry_run=False):
        """
        Ensures that all the necessary SoftwareProducts and SoftwareProductRates are created for the plan.
        """
        logging.info('Ensuring Products and Product Rates')

        product = SoftwareProduct(name='%s %s' % (product_type, edition), product_type=product_type)
        product_rates = []
        for product_rate in self.BOOTSTRAP_PRODUCT_RATES[edition]:
            if dry_run:
                logging.info("[DRY RUN] Creating Product: %s" % product)
                logging.info("[DRY RUN] Corresponding product rate of $%d created." % product_rate.monthly_fee)
            else:
                try:
                    product = SoftwareProduct.objects.get(name=product.name)
                    logging.info("Product '%s' already exists. Using existing product to add rate." % product.name)
                except ObjectDoesNotExist:
                    product.save()
                    logging.info("Creating Product: %s" % product)
                product_rate.product = product
                product_rate.save()
                logging.info("Corresponding product rate of $%d created." % product_rate.monthly_fee)
            product_rates.append(product_rate)
        return product, product_rates

    def ensure_features(self, dry_run=False):
        """
        Ensures that all the Features necessary for the plans are created.
        """
        logging.info('Ensuring Features')

        edition_to_features = defaultdict(list)
        for edition in self.editions:
            for feature_type in self.feature_types:
                feature = Feature(name='%s %s' % (feature_type, edition), feature_type=feature_type)
                if dry_run:
                    logging.info("[DRY RUN] Creating Feature: %s" % feature)
                else:
                    try:
                        feature = Feature.objects.get(name=feature.name)
                        logging.info("Feature '%s' already exists. Using existing feature to add rate." % feature.name)
                    except ObjectDoesNotExist:
                        feature.save()
                        logging.info("Creating Feature: %s" % feature)
                edition_to_features[edition].append(feature)
        return edition_to_features

    def ensure_feature_rates(self, features, edition, dry_run=False):
        """
        Ensures that all the FeatureRates necessary for the plans are created.
        """
        logging.info('Ensuring Feature Rates')

        feature_rates = []
        for feature in features:
            feature_rate = self.BOOTSTRAP_FEATURE_RATES[edition][feature.feature_type]
            if dry_run:
                logging.info("[DRY RUN] Creating rate for feature '%s': %s" % (feature.name, feature_rate))
            else:
                feature_rate.feature = feature
                feature_rate.save()
                logging.info("Creating rate for feature '%s': %s" % (feature.name, feature_rate))
            feature_rates.append(feature_rate)
        return feature_rates

    BOOTSTRAP_EDITION_TO_ROLE = {
        SoftwarePlanEdition.COMMUNITY: 'community_plan_v0',
        SoftwarePlanEdition.STANDARD: 'standard_plan_v0',
        SoftwarePlanEdition.PRO: 'pro_plan_v0',
        SoftwarePlanEdition.ADVANCED: 'advanced_plan_v0',
    }

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
    }

    BOOTSTRAP_FEATURE_RATES = {
        SoftwarePlanEdition.COMMUNITY: {
            FeatureType.USER: FeatureRate(monthly_limit=50, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=0),  # use defaults here
        },
        SoftwarePlanEdition.STANDARD: {
            FeatureType.USER: FeatureRate(monthly_limit=100, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=250),
        },
        SoftwarePlanEdition.PRO: {
            FeatureType.USER: FeatureRate(monthly_limit=500, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=500),
        },
        SoftwarePlanEdition.ADVANCED: {
            FeatureType.USER: FeatureRate(monthly_limit=1000, per_excess_fee=Decimal('1.00')),
            FeatureType.SMS: FeatureRate(monthly_limit=1000),
        },
    }
