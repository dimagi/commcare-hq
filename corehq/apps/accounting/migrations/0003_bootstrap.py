# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from collections import defaultdict
from decimal import Decimal
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import models, migrations

from corehq.apps.accounting.models import (
    SoftwareProductType, SoftwarePlanEdition, SoftwarePlanVisibility, FeatureType,
)

logger = logging.getLogger(__name__)


def bootstrap_software_plans(apps, schema_editor):
    BootstrapSoftwarePlans(apps).bootstrap()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0002_update_pricing_table'),
    ]

    operations = [
        migrations.RunPython(bootstrap_software_plans),
    ]


class BootstrapSoftwarePlans(object):
    """
    This is a direct copy of the cchq_software_plan_bootstrap management command
    so that orm can be used to reference the objects.
    """
    def __init__(self, apps):
        self.apps = apps
        self.verbose = False
        self.for_tests = False

    @property
    def SoftwarePlanVersion(self):
        return self.apps.get_model('accounting', 'SoftwarePlanVersion')

    @property
    def SoftwarePlan(self):
        return self.apps.get_model('accounting', 'SoftwarePlan')

    @property
    def SoftwareProduct(self):
        return self.apps.get_model('accounting', 'SoftwareProduct')

    @property
    def SoftwareProductRate(self):
        return self.apps.get_model('accounting', 'SoftwareProductRate')

    @property
    def DefaultProductPlan(self):
        return self.apps.get_model('accounting', 'DefaultProductPlan')

    @property
    def Feature(self):
        return self.apps.get_model('accounting', 'Feature')

    @property
    def FeatureRate(self):
        return self.apps.get_model('accounting', 'FeatureRate')

    def bootstrap(self):
        logger.info('Bootstrapping standard plans. Enterprise plans will have to be created via the admin UIs.')

        self.product_types = [p[0] for p in SoftwareProductType.CHOICES]
        self.editions = [
            SoftwarePlanEdition.COMMUNITY,
            SoftwarePlanEdition.STANDARD,
            SoftwarePlanEdition.PRO,
            SoftwarePlanEdition.ADVANCED,
            SoftwarePlanEdition.ENTERPRISE,
        ]
        self.feature_types = [f[0] for f in FeatureType.CHOICES]
        self.ensure_plans()

    def ensure_plans(self, dry_run=False):
        edition_to_features = self.ensure_features(dry_run=dry_run)
        for product_type in self.product_types:
            for edition in self.editions:
                role_slug = self.BOOTSTRAP_EDITION_TO_ROLE[edition]
                try:
                    role = self.apps.get_model('django_prbac', 'Role').objects.get(slug=role_slug)
                except ObjectDoesNotExist:
                    logger.info("Could not find the role '%s'. Did you forget to run cchq_prbac_bootstrap?")
                    logger.info("Aborting. You should figure this out.")
                    return
                software_plan_version = self.SoftwarePlanVersion(role=role)

                product, product_rates = self.ensure_product_and_rate(product_type, edition, dry_run=dry_run)
                feature_rates = self.ensure_feature_rates(edition_to_features[edition], edition, dry_run=dry_run)
                software_plan = self.SoftwarePlan(
                    name='%s Edition' % product.name, edition=edition, visibility=SoftwarePlanVisibility.PUBLIC
                )
                if dry_run:
                    logger.info("[DRY RUN] Creating Software Plan: %s" % software_plan.name)
                else:
                    try:
                        software_plan = self.SoftwarePlan.objects.get(name=software_plan.name)
                        if self.verbose:
                            logger.info("Plan '%s' already exists. Using existing plan to add version."
                                        % software_plan.name)
                    except self.SoftwarePlan.DoesNotExist:
                        software_plan.save()
                        if self.verbose:
                            logger.info("Creating Software Plan: %s" % software_plan.name)

                        software_plan_version.plan = software_plan
                        software_plan_version.save()
                        for product_rate in product_rates:
                            product_rate.save()
                            software_plan_version.product_rates.add(product_rate)
                        for feature_rate in feature_rates:
                            feature_rate.save()
                            software_plan_version.feature_rates.add(feature_rate)
                        software_plan_version.save()

                default_product_plan = self.DefaultProductPlan(product_type=product.product_type, edition=edition)
                if dry_run:
                    logger.info("[DRY RUN] Setting plan as default for product '%s' and edition '%s'." %
                                 (product.product_type, default_product_plan.edition))
                else:
                    try:
                        default_product_plan = self.DefaultProductPlan.objects.get(
                            product_type=product.product_type, edition=edition,
                            is_trial=False
                        )
                        if self.verbose:
                            logger.info("Default for product '%s' and edition "
                                        "'%s' already exists." % (
                                product.product_type, default_product_plan.edition
                            ))
                    except ObjectDoesNotExist:
                        default_product_plan.plan = software_plan
                        default_product_plan.save()
                        if self.verbose:
                            logger.info("Setting plan as default for product '%s' and edition '%s'." %
                                        (product.product_type,
                                         default_product_plan.edition))

    def ensure_product_and_rate(self, product_type, edition, dry_run=False):
        """
        Ensures that all the necessary SoftwareProducts and SoftwareProductRates are created for the plan.
        """
        if self.verbose:
            logger.info('Ensuring Products and Product Rates')

        product = self.SoftwareProduct(name='%s %s' % (product_type, edition), product_type=product_type)
        if edition == SoftwarePlanEdition.ENTERPRISE:
            product.name = "Dimagi Only %s" % product.name

        product_rates = []
        BOOTSTRAP_PRODUCT_RATES = {
            SoftwarePlanEdition.COMMUNITY: [
                self.SoftwareProductRate(),  # use all the defaults
            ],
            SoftwarePlanEdition.STANDARD: [
                self.SoftwareProductRate(monthly_fee=Decimal('100.00')),
            ],
            SoftwarePlanEdition.PRO: [
                self.SoftwareProductRate(monthly_fee=Decimal('500.00')),
            ],
            SoftwarePlanEdition.ADVANCED: [
                self.SoftwareProductRate(monthly_fee=Decimal('1000.00')),
            ],
            SoftwarePlanEdition.ENTERPRISE: [
                self.SoftwareProductRate(monthly_fee=Decimal('0.00')),
            ],
        }

        for product_rate in BOOTSTRAP_PRODUCT_RATES[edition]:
            if dry_run:
                logger.info("[DRY RUN] Creating Product: %s" % product)
                logger.info("[DRY RUN] Corresponding product rate of $%d created." % product_rate.monthly_fee)
            else:
                try:
                    product = self.SoftwareProduct.objects.get(name=product.name)
                    if self.verbose:
                        logger.info("Product '%s' already exists. Using "
                                    "existing product to add rate."
                                    % product.name)
                except self.SoftwareProduct.DoesNotExist:
                    product.save()
                    if self.verbose:
                        logger.info("Creating Product: %s" % product)
                if self.verbose:
                    logger.info("Corresponding product rate of $%d created."
                                % product_rate.monthly_fee)
            product_rate.product = product
            product_rates.append(product_rate)
        return product, product_rates

    def ensure_features(self, dry_run=False):
        """
        Ensures that all the Features necessary for the plans are created.
        """
        if self.verbose:
            logger.info('Ensuring Features')

        edition_to_features = defaultdict(list)
        for edition in self.editions:
            for feature_type in self.feature_types:
                feature = self.Feature(name='%s %s' % (feature_type, edition), feature_type=feature_type)
                if edition == SoftwarePlanEdition.ENTERPRISE:
                    feature.name = "Dimagi Only %s" % feature.name
                if dry_run:
                    logger.info("[DRY RUN] Creating Feature: %s" % feature)
                else:
                    try:
                        feature = self.Feature.objects.get(name=feature.name)
                        if self.verbose:
                            logger.info("Feature '%s' already exists. Using "
                                        "existing feature to add rate."
                                        % feature.name)
                    except ObjectDoesNotExist:
                        feature.save()
                        if self.verbose:
                            logger.info("Creating Feature: %s" % feature)
                edition_to_features[edition].append(feature)
        return edition_to_features

    def ensure_feature_rates(self, features, edition, dry_run=False):
        """
        Ensures that all the FeatureRates necessary for the plans are created.
        """
        if self.verbose:
            logger.info('Ensuring Feature Rates')

        feature_rates = []
        BOOTSTRAP_FEATURE_RATES = {
            SoftwarePlanEdition.COMMUNITY: {
                FeatureType.USER: self.FeatureRate(monthly_limit=2 if self.for_tests else 50,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.FeatureRate(monthly_limit=0),  # use defaults here
            },
            SoftwarePlanEdition.STANDARD: {
                FeatureType.USER: self.FeatureRate(monthly_limit=4 if self.for_tests else 100,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.FeatureRate(monthly_limit=3 if self.for_tests else 100),
            },
            SoftwarePlanEdition.PRO: {
                FeatureType.USER: self.FeatureRate(monthly_limit=6 if self.for_tests else 500,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.FeatureRate(monthly_limit=5 if self.for_tests else 500),
            },
            SoftwarePlanEdition.ADVANCED: {
                FeatureType.USER: self.FeatureRate(monthly_limit=8 if self.for_tests else 1000,
                                              per_excess_fee=Decimal('1.00')),
                FeatureType.SMS: self.FeatureRate(monthly_limit=7 if self.for_tests else 1000),
            },
            SoftwarePlanEdition.ENTERPRISE: {
                FeatureType.USER: self.FeatureRate(monthly_limit=-1, per_excess_fee=Decimal('0.00')),
                FeatureType.SMS: self.FeatureRate(monthly_limit=-1),
            },
        }
        for feature in features:
            feature_rate = BOOTSTRAP_FEATURE_RATES[edition][feature.feature_type]
            feature_rate.feature = feature
            if dry_run:
                logger.info("[DRY RUN] Creating rate for feature '%s': %s" % (feature.name, feature_rate))
            elif self.verbose:
                logger.info("Creating rate for feature '%s': %s" % (feature.name, feature_rate))
            feature_rates.append(feature_rate)
        return feature_rates

    BOOTSTRAP_EDITION_TO_ROLE = {
        SoftwarePlanEdition.COMMUNITY: 'community_plan_v0',
        SoftwarePlanEdition.STANDARD: 'standard_plan_v0',
        SoftwarePlanEdition.PRO: 'pro_plan_v0',
        SoftwarePlanEdition.ADVANCED: 'advanced_plan_v0',
        SoftwarePlanEdition.ENTERPRISE: 'enterprise_plan_v0',
    }
