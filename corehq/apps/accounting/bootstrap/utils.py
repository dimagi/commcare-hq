from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
)
from corehq.apps.accounting.utils import (
    log_accounting_error,
    log_accounting_info,
)

FEATURE_TYPES = list(dict(FeatureType.CHOICES))


def ensure_plans(config, verbose, apps):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    SoftwarePlan = apps.get_model('accounting', 'SoftwarePlan')
    SoftwarePlanVersion = apps.get_model('accounting', 'SoftwarePlanVersion')
    Role = apps.get_model('django_prbac', 'Role')

    for plan_key, plan_deets in config.items():
        edition, is_trial, is_report_builder_enabled = plan_key
        features = _ensure_features(edition, verbose, apps)
        try:
            role = _ensure_role(plan_deets['role'], apps)
        except Role.DoesNotExist:
            return

        product, product_rate = _ensure_product_rate(
            plan_deets['product_rate_monthly_fee'], edition,
            verbose=verbose, apps=apps,
        )
        feature_rates = _ensure_feature_rates(
            plan_deets['feature_rates'], features, edition,
            verbose=verbose, apps=apps,
        )

        software_plan = SoftwarePlan(
            name=(
                (('%s Trial' % product_rate.name) if is_trial else ('%s Edition' % product_rate.name))
                if product is None else product.name  # TODO - remove after squashing migrations
            ),
            edition=edition,
            visibility=SoftwarePlanVisibility.PUBLIC
        )
        if is_report_builder_enabled:
            software_plan.name = '%s - Report Builder (5 Reports)' % software_plan.name

        try:
            software_plan = SoftwarePlan.objects.get(name=software_plan.name)
            if verbose:
                log_accounting_info(
                    "Plan '%s' already exists. Using existing plan to add version." % software_plan.name
                )
        except SoftwarePlan.DoesNotExist:
            software_plan.save()
            if verbose:
                log_accounting_info("Creating Software Plan: %s" % software_plan.name)

        product_rate.save()
        software_plan_version = SoftwarePlanVersion(role=role, plan=software_plan, product_rate=product_rate)
        software_plan_version.save()

        for feature_rate in feature_rates:
            feature_rate.save()
            software_plan_version.feature_rates.add(feature_rate)
        software_plan_version.save()

        try:
            default_product_plan = DefaultProductPlan.objects.get(
                edition=edition,
                is_trial=is_trial,
                is_report_builder_enabled=is_report_builder_enabled,
            )
            if verbose:
                log_accounting_info(
                    "Default for edition '%s' with is_trial='%s' already exists."
                    % (default_product_plan.edition, is_trial)
                )
        except DefaultProductPlan.DoesNotExist:
            default_product_plan = DefaultProductPlan(
                edition=edition,
                is_trial=is_trial,
                is_report_builder_enabled=is_report_builder_enabled,
            )
        finally:
            default_product_plan.plan = software_plan
            default_product_plan.save()
            if verbose:
                log_accounting_info(
                    "Setting plan as default for edition '%s' with is_trial='%s'."
                    % (default_product_plan.edition, is_trial)
                )

    _clear_cache(SoftwarePlan.objects.all(), DefaultProductPlan.objects.all())


def _ensure_role(role_slug, apps):
    Role = apps.get_model('django_prbac', 'Role')
    try:
        role = Role.objects.get(slug=role_slug)
    except Role.DoesNotExist:
        log_accounting_error(
            "Could not find the role '%s'. Did you forget to run cchq_prbac_bootstrap?"
            % role_slug
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

    product_name = 'CommCare %s' % edition
    if edition == SoftwarePlanEdition.ENTERPRISE:
        product_name = "Dimagi Only %s" % product_name

    product_rate = SoftwareProductRate(monthly_fee=monthly_fee)
    try:
        # TODO - remove after squashing migrations
        SoftwareProduct = apps.get_model('accounting', 'SoftwareProduct')
        product = SoftwareProduct(name=product_name, product_type='CommCare')
        try:
            product = SoftwareProduct.objects.get(name=product.name)
            if verbose:
                log_accounting_info(
                    "Product '%s' already exists. Using existing product to add rate."
                    % product.name
                )
        except SoftwareProduct.DoesNotExist:
            if verbose:
                log_accounting_info("Creating Product: %s" % product)
            product.save()
        product_rate.product = product

        if verbose:
            log_accounting_info("Corresponding product rate of $%d created." % product_rate.monthly_fee)

        return product, product_rate

    except LookupError:
        product_rate.name = product_name
        if verbose:
            log_accounting_info("Corresponding product rate of $%d created." % product_rate.monthly_fee)
        return None, product_rate  # TODO - don't return tuple after squashing migrations


def _ensure_features(edition, verbose, apps):
    """
    Ensures that all the Features necessary for the plans are created.
    """
    Feature = apps.get_model('accounting', 'Feature')

    if verbose:
        log_accounting_info('Ensuring Features for plan: %s' % edition)

    features = []
    for feature_type in FEATURE_TYPES:
        # Don't prefix web user feature name with edition
        if feature_type == FeatureType.WEB_USER:
            feature = Feature(name=feature_type, feature_type=feature_type)
        else:
            feature = Feature(name='%s %s' % (feature_type, edition), feature_type=feature_type)
            if edition == SoftwarePlanEdition.ENTERPRISE:
                feature.name = "Dimagi Only %s" % feature.name
        try:
            feature = Feature.objects.get(name=feature.name)
            if verbose:
                log_accounting_info(
                    "Feature '%s' already exists. Using existing feature to add rate."
                    % feature.name
                )
        except Feature.DoesNotExist:
            feature.save()
            if verbose:
                log_accounting_info("Creating Feature: %s" % feature)
        features.append(feature)
    return features


def _ensure_feature_rates(feature_rates, features, edition, verbose, apps):
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
            log_accounting_info("Creating rate for feature '%s': %s" % (feature.name, feature_rate))
        db_feature_rates.append(feature_rate)
    return db_feature_rates


def _clear_cache(software_plans, default_plans):
    from corehq.apps.accounting.models import SoftwarePlan, DefaultProductPlan
    for software_plan in software_plans:
        SoftwarePlan.get_version.clear(software_plan)
    for plan in default_plans:
        DefaultProductPlan.get_default_plan_version.clear(
            DefaultProductPlan, plan.edition, plan.is_trial, plan.is_report_builder_enabled,
        )
