from collections import namedtuple

from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
)
from corehq.apps.accounting.utils import (
    log_accounting_error,
    log_accounting_info,
)


def ensure_plans(config, verbose, apps):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    SoftwarePlan = apps.get_model('accounting', 'SoftwarePlan')
    Role = apps.get_model('django_prbac', 'Role')
    PlanKey = namedtuple('PlanKey', ['edition', 'is_trial', 'is_report_builder_enabled', 'is_annual_plan'],
                     defaults=('is_annual_plan', None))

    for plan_key, plan_deets in config.items():
        plan_key = PlanKey(*plan_key)
        try:
            role = _ensure_role(plan_deets['role'], apps)
        except Role.DoesNotExist:
            return

        product, product_rate = _ensure_product_rate(
            plan_deets['product_rate_monthly_fee'], plan_key.edition,
            verbose=verbose, apps=apps,
        )
        features = _ensure_features(plan_deets['feature_rates'], plan_key.edition, verbose, apps)
        feature_rates = ensure_feature_rates(plan_deets['feature_rates'], features, verbose=verbose, apps=apps)

        software_plan = _ensure_software_plan(plan_key, product, product_rate, verbose, apps)
        _ensure_software_plan_version(role, software_plan, product_rate, feature_rates, apps)
        _ensure_default_product_plan(plan_key, software_plan, verbose, apps)

    _clear_cache(SoftwarePlan.objects.all(), DefaultProductPlan.objects.all())


def _ensure_role(role_slug, apps):
    Role = apps.get_model('django_prbac', 'Role')
    try:
        role = Role.objects.get(slug=role_slug)
    except Role.DoesNotExist:
        log_accounting_error(
            f"Could not find the role '{role_slug}'. Did you forget to run cchq_prbac_bootstrap?"
        )
        log_accounting_error("Aborting. You should figure this out.")
        raise
    return role


def _ensure_product_rate(monthly_fee, edition, verbose, apps):
    """
    Ensures that all the necessary SoftwareProductRates are created for the plan.
    """
    if verbose:
        log_accounting_info('Ensuring Product Rates')

    SoftwareProductRate = apps.get_model('accounting', 'SoftwareProductRate')

    product_name = f"CommCare {edition}"
    if edition == SoftwarePlanEdition.ENTERPRISE:
        product_name = f"Dimagi Only {product_name}"

    product_rate = SoftwareProductRate(monthly_fee=monthly_fee)
    try:
        product = _get_software_product(product_name, verbose, apps)
        product_rate.product = product
    except LookupError:
        product = None
        product_rate.name = product_name

    product_rate.save()
    if verbose:
        log_accounting_info(f"Corresponding product rate of {product_rate.monthly_fee} created.")

    return product, product_rate


def _get_software_product(product_name, verbose, apps):
    # SoftwareProduct no longer exists but is retained here to avoid breaking old migrations
    SoftwareProduct = apps.get_model('accounting', 'SoftwareProduct')
    product = SoftwareProduct(name=product_name, product_type='CommCare')
    try:
        product = SoftwareProduct.objects.get(name=product.name)
        if verbose:
            log_accounting_info(
                f"Product '{product.name}' already exists. Using existing product to add rate."
            )
    except SoftwareProduct.DoesNotExist:
        if verbose:
            log_accounting_info(f"Creating Product: {product}")
        product.save()
    return product


def _ensure_features(feature_rates, edition, verbose, apps):
    """
    Ensures that all the Features necessary for the plans are created.
    """
    Feature = apps.get_model('accounting', 'Feature')

    if verbose:
        log_accounting_info(f"Ensuring Features for plan: {edition}")

    features = []
    for feature_type in feature_rates.keys():
        if feature_type in FeatureType.EDITIONED_FEATURES:
            feature_name = f"{feature_type} {edition}"
            if edition == SoftwarePlanEdition.ENTERPRISE:
                feature_name = f"Dimagi Only {feature_name}"
        else:
            feature_name = feature_type
        try:
            feature = Feature.objects.get(name=feature_name)
            if verbose:
                log_accounting_info(
                    f"Feature '{feature.name}' already exists. Using existing feature to add rate."
                )
        except Feature.DoesNotExist:
            feature = Feature.objects.create(name=feature_name, feature_type=feature_type)
            if verbose:
                log_accounting_info(f"Creating Feature: {feature}")
        features.append(feature)
    return features


def ensure_feature_rates(feature_rates, features, verbose, apps):
    """
    Ensures that all the FeatureRates necessary for the plans are created.
    """
    FeatureRate = apps.get_model('accounting', 'FeatureRate')

    if verbose:
        log_accounting_info('Ensuring Feature Rates')

    db_feature_rates = []
    for feature in features:
        # web user feature rate is not included in all plans
        # if current plan doesn't have web user feature rate, skip
        try:
            feature_rate = FeatureRate(**feature_rates[feature.feature_type])
        except KeyError:
            continue
        feature_rate.feature = feature
        if verbose:
            log_accounting_info(f"Creating rate for feature '{feature.name}': {feature_rate}")
        db_feature_rates.append(feature_rate)
    return db_feature_rates


def _ensure_software_plan(plan_key, product, product_rate, verbose, apps):
    SoftwarePlan = apps.get_model('accounting', 'SoftwarePlan')
    plan_name = _software_plan_name(plan_key, product, product_rate)
    try:
        software_plan = SoftwarePlan.objects.get(name=plan_name)
        if verbose:
            log_accounting_info(
                f"Plan '{software_plan.name}' already exists. Using existing plan to add version."
            )
    except SoftwarePlan.DoesNotExist:
        plan_opts = {
            'name': plan_name,
            'edition': plan_key.edition,
            'visibility': (SoftwarePlanVisibility.INTERNAL
                if plan_key.edition == SoftwarePlanEdition.ENTERPRISE
                else SoftwarePlanVisibility.PUBLIC),
        }
        if plan_key.is_annual_plan is not None:
            plan_opts['is_annual_plan'] = plan_key.is_annual_plan
        software_plan = SoftwarePlan.objects.create(**plan_opts)
        if verbose:
            log_accounting_info(f"Creating Software Plan: {software_plan.name}")
    return software_plan


def _software_plan_name(plan_key, product, product_rate):
    name_parts = [
        product_rate.name if product is None else product.name,
        (" Trial" if plan_key.is_trial else " Edition") if product is None else "",
    ]
    if plan_key.edition in SoftwarePlanEdition.SELF_RENEWABLE_EDITIONS:
        name_parts.extend([
            " - Pay Annually" if plan_key.is_annual_plan else " - Pay Monthly",
            " - Report Builder (5 Reports)" if plan_key.is_report_builder_enabled else "",
        ])
    return "".join(name_parts)


def _ensure_software_plan_version(role, software_plan, product_rate, feature_rates, apps):
    SoftwarePlanVersion = apps.get_model('accounting', 'SoftwarePlanVersion')

    software_plan_version = SoftwarePlanVersion(role=role, plan=software_plan, product_rate=product_rate)
    software_plan_version.save()

    for feature_rate in feature_rates:
        feature_rate.save()
        software_plan_version.feature_rates.add(feature_rate)
    software_plan_version.save()
    return software_plan_version


def _ensure_default_product_plan(plan_key, software_plan, verbose, apps):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    plan_opts = {
        'edition': plan_key.edition,
        'is_trial': plan_key.is_trial,
        'is_report_builder_enabled': plan_key.is_report_builder_enabled,
    }
    if plan_key.is_annual_plan is not None:
        plan_opts['is_annual_plan'] = plan_key.is_annual_plan

    try:
        default_product_plan = DefaultProductPlan.objects.get(**plan_opts)
        if verbose:
            log_accounting_info(
                f"Default for edition '{default_product_plan.edition}' "
                f"with is_trial='{plan_key.is_trial}' "
                f"and is_annual_plan='{plan_key.is_annual_plan}' already exists."
            )
    except DefaultProductPlan.DoesNotExist:
        default_product_plan = DefaultProductPlan(**plan_opts)
    finally:
        default_product_plan.plan = software_plan
        default_product_plan.save()
        if verbose:
            log_accounting_info(
                f"Setting plan as default for edition '{default_product_plan.edition}' "
                f"with is_trial='{plan_key.is_trial}' "
                f"and is_annual_plan='{plan_key.is_annual_plan}'."
            )
    return default_product_plan


def _clear_cache(software_plans, default_plans):
    from corehq.apps.accounting.models import SoftwarePlan, DefaultProductPlan
    for software_plan in software_plans:
        SoftwarePlan.get_version.clear(software_plan)
    for plan in default_plans:
        DefaultProductPlan.get_default_plan_version.clear(
            DefaultProductPlan, plan.edition, plan.is_trial, plan.is_report_builder_enabled,
        )
