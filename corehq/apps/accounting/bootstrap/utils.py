# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

import logging
from collections import defaultdict

from corehq.apps.accounting.exceptions import AccountingError
from corehq.apps.accounting.models import (
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    SoftwareProductType,
)

logger = logging.getLogger(__name__)


PRODUCT_TYPES = [
    SoftwareProductType.COMMCARE,
    SoftwareProductType.COMMCONNECT,
    SoftwareProductType.COMMTRACK,
]


def ensure_plans(edition_to_role, edition_to_product_rate, edition_to_feature_rate, feature_types,
                 dry_run, verbose, apps):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    SoftwarePlan = apps.get_model('accounting', 'SoftwarePlan')
    SoftwarePlanVersion = apps.get_model('accounting', 'SoftwarePlanVersion')
    Role = apps.get_model('django_prbac', 'Role')

    editions = edition_to_role.keys()
    edition_to_features = _ensure_features(feature_types, editions, dry_run=dry_run, verbose=verbose, apps=apps)
    for product_type in PRODUCT_TYPES:
        for edition in editions:
            role_slug = edition_to_role[edition]
            try:
                role = Role.objects.get(slug=role_slug)
            except Role.DoesNotExist:
                logger.info("Could not find the role '%s'. Did you forget to run cchq_prbac_bootstrap?")
                logger.info("Aborting. You should figure this out.")
                return
            software_plan_version = SoftwarePlanVersion(role=role)

            product, product_rate = _ensure_product_and_rate(
                edition_to_product_rate, product_type, edition,
                dry_run=dry_run, verbose=verbose, apps=apps,
            )
            feature_rates = _ensure_feature_rates(
                edition_to_feature_rate, edition_to_features[edition], edition,
                dry_run=dry_run, verbose=verbose, apps=apps,
            )
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

                product_rate.save()
                if hasattr(SoftwarePlanVersion, 'product_rates'):
                    software_plan_version.product_rates.add(product_rate)
                elif hasattr(SoftwarePlanVersion, 'product_rate'):
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


def _ensure_product_and_rate(edition_to_product_rate, product_type, edition, dry_run, verbose, apps):
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

    product_rate = SoftwareProductRate(**edition_to_product_rate[edition])
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
    return product, product_rate


def _ensure_features(feature_types, editions, dry_run, verbose, apps):
    """
    Ensures that all the Features necessary for the plans are created.
    """
    Feature = apps.get_model('accounting', 'Feature')

    if verbose:
        logger.info('Ensuring Features')

    edition_to_features = defaultdict(list)
    for edition in editions:
        for feature_type in feature_types:
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


def _ensure_feature_rates(edition_to_feature_rate, features, edition, dry_run, verbose, apps):
    """
    Ensures that all the FeatureRates necessary for the plans are created.
    """
    FeatureRate = apps.get_model('accounting', 'FeatureRate')

    if verbose:
        logger.info('Ensuring Feature Rates')

    feature_rates = []
    for feature in features:
        feature_rate = FeatureRate(**edition_to_feature_rate[edition][feature.feature_type])
        feature_rate.feature = feature
        if dry_run:
            logger.info("[DRY RUN] Creating rate for feature '%s': %s" % (feature.name, feature_rate))
        elif verbose:
            logger.info("Creating rate for feature '%s': %s" % (feature.name, feature_rate))
        feature_rates.append(feature_rate)
    return feature_rates
