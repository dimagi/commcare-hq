import logging
from collections import defaultdict

from django.core.management import BaseCommand

from django_prbac.models import Grant, Role

from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    change_role_for_software_plan_version,
)
from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanVersion,
    SoftwarePlanVisibility,
    Subscription,
)
from corehq.apps.linked_domain.models import DomainLink

logger = logging.getLogger(__name__)

NEW_ROLE_SLUG_SUFFIX = "_erm"
NEW_NAME_SUFFIX = " (With ERM)"


class RoleMissingPrivilege(Exception):
    pass


class ExistingRoleNotFound(Exception):
    pass


class PrivilegeRoleDoesNotExist(Exception):
    pass


class Command(BaseCommand):
    """
    Enables the RELEASE_MANAGEMENT privilege on any domain that has the Linked Projects feature flag enabled
    """

    def add_arguments(self, parser):
        parser.add_argument('-q', '--quiet', help="Quiet output to warnings/errors only")
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, quiet, dry_run, **options):
        logger.setLevel(logging.WARNING if quiet else logging.INFO)
        privilege_role_slug = 'release_management'
        active_roles = _get_active_roles()
        roles_to_update, versions_to_update, plans_to_create = _get_migration_info(
            active_roles, privilege_role_slug
        )
        _update_roles_in_place(roles_to_update, privilege_role_slug, dry_run=dry_run)
        _update_versions_in_place(versions_to_update, privilege_role_slug, dry_run=dry_run)
        _update_subscriptions_to_new_plans(plans_to_create, privilege_role_slug, dry_run=dry_run)


def _get_migration_info(roles, privilege_slug):
    """
    :param roles: [Role]
    :param toggle_slug: str slug for feature flag to migrate from
    :param privilege_slug: str slug for role replaces feature flag
    :return: a list of role slugs that can be updated directly
    """
    try:
        privilege_role = Role.objects.get(slug=privilege_slug)
    except Role.DoesNotExist:
        raise PrivilegeRoleDoesNotExist

    roles_to_update = []
    plan_versions_to_update = []
    plans_to_create = defaultdict(list)
    for role in roles:
        # skip public enterprise roles since they are handled in a separate migration
        if _should_skip_role(role, privilege_role, roles_to_skip=['enterprise_plan_v0', 'enterprise_plan_v1']):
            continue

        versions = SoftwarePlanVersion.objects.filter(role=role, is_active=True)
        domains = _get_domains_for_versions(versions)

        if not _contain_public_versions(versions) and _all_domains_use_linked_domains(domains):
            roles_to_update.append(role.slug)
            formatted_domains = '\n'.join(domains)
            logger.info(f'[ERM Migration]Will update role {role.slug} for domains:\n{formatted_domains}')
            continue

        for version in versions:
            domains_for_version = _get_domains_for_version(version)
            if _all_domains_use_linked_domains(domains_for_version):
                plan_versions_to_update.append(version.id)
                formatted_domains = '\n'.join(domains_for_version)
                logger.info(f'[ERM Migration]Will update plan version {version.id} for domains:\n{formatted_domains}')
            else:
                domains_that_use_feature = _get_domains_that_use_linked_domains(domains_for_version)
                if domains_that_use_feature:
                    formatted_domains = '\n'.join(domains_that_use_feature)
                    logger.info(f'[ERM Migration]Will update plan for version {version.id} for domains:\n{formatted_domains}')
                    plans_to_create[version.id] = domains_that_use_feature

    return roles_to_update, plan_versions_to_update, plans_to_create


def _contain_public_versions(versions):
    plan_visibility = {version.plan.visibility for version in versions}
    return SoftwarePlanVisibility.PUBLIC in plan_visibility


def _get_domains_that_use_linked_domains(domains):
    domains_in_links = _get_all_domains_using_linked_domains()
    return list(domains_in_links & set(domains))


def _all_domains_use_linked_domains(domains):
    domains_in_links = _get_all_domains_using_linked_domains()
    return set(domains).issubset(domains_in_links)


def _get_all_domains_using_linked_domains():
    domains_in_links = DomainLink.all_objects.all()
    upstream_domains = [d.master_domain for d in domains_in_links]
    downstream_domains = [d.linked_domain for d in domains_in_links]
    return set(upstream_domains + downstream_domains)


def _get_domains_for_version(version):
    return [
        sub.subscriber.domain for sub in Subscription.visible_objects.filter(plan_version=version, is_active=True)
    ]


def _get_domains_for_versions(versions):
    return [
        sub.subscriber.domain for version in versions
        for sub in Subscription.visible_objects.filter(plan_version=version, is_active=True)
    ]


def _should_skip_role(role_to_check, privilege_role, roles_to_skip=None):
    # skip roles that already have existing Grant with privilege role
    if Grant.objects.filter(from_role=role_to_check, to_role=privilege_role).exists():
        return True

    if roles_to_skip and role_to_check.slug in roles_to_skip:
        return True

    return False


def _get_active_roles():
    active_plan_versions = SoftwarePlanVersion.objects.filter(is_active=True)
    # roles referenced by active software plans as a set (remove duplicates)
    return {version.role for version in active_plan_versions}


def _update_roles_in_place(role_slugs, privilege_slug, dry_run=False):
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    for role_slug in role_slugs:
        role = Role.objects.get(slug=role_slug)
        role_for_privilege = Role.objects.get(slug=privilege_slug)
        if not dry_run:
            Grant.objects.create(from_role=role, to_role=role_for_privilege)
        logger.info(f'{dry_run_tag}Created grant from {role.slug} to {privilege_slug}.')


def _update_versions_in_place(version_ids, privilege_slug, dry_run=False):
    for version_id in version_ids:
        version = SoftwarePlanVersion.objects.get(id=version_id)
        new_role = _get_or_create_role_with_privilege(version.role.slug, privilege_slug, dry_run=dry_run)
        if new_role and not dry_run:
            if not dry_run:
                change_role_for_software_plan_version(
                    version.role.slug, new_role.slug, limit_to_plan_version_id=version_id
                )
            else:
                # change_role_for_software_plan_version raises an exception in dry_run mode
                logger.info(f'Modified role from {version.role.slug} to {new_role.slug} for version {version_id}.')


def _update_subscriptions_to_new_plans(domains_by_plan_version, privilege_slug, dry_run=False):
    """
    :param domains_by_plan_version: {'<plan_version_id>': [domains_for_version]}
    :param privilege_slug: slug for Role obj representing privilege to add
    """
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    for version_id, domains in domains_by_plan_version.items():
        current_version = SoftwarePlanVersion.objects.get(id=version_id)
        current_plan = current_version.plan

        new_role = _get_or_create_role_with_privilege(current_version.role.slug, privilege_slug, dry_run=dry_run)
        new_plan = _get_or_create_new_software_plan(current_plan, dry_run=dry_run)
        new_version = _get_or_create_new_software_plan_version(
            new_plan, current_version, new_role, dry_run=dry_run
        )

        if new_role and new_plan and new_version:
            for domain in domains:
                subscription = Subscription.get_active_subscription_by_domain(domain)
                subscription.plan_version = new_plan.get_version()
                if not dry_run:
                    subscription.save()
                logger.info(f'{dry_run_tag}Updated subscription\'s software plan to {new_plan.name} for {domain}.')


def _get_or_create_new_software_plan(from_plan, dry_run=False):
    """
    :param from_plan: plan to copy attributes from
    :param dry_run: if True, will not make changes to the db
    :return: newly created SoftwarePlan
    """
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    new_name = from_plan.name + NEW_NAME_SUFFIX
    try:
        plan = SoftwarePlan.objects.get(name=new_name)
    except SoftwarePlan.DoesNotExist:
        plan = SoftwarePlan(
            name=new_name,
            description=from_plan.description,
            edition=from_plan.edition,
            visibility=from_plan.visibility,
            is_customer_software_plan=from_plan.is_customer_software_plan,
            max_domains=from_plan.max_domains,
            is_annual_plan=from_plan.is_annual_plan,
        )
        logger.info(f"{dry_run_tag}Created new software plan {plan.name} from existing plan {from_plan.name}.")
    else:
        logger.info(f"{dry_run_tag}Found existing software plan {plan.name}.")

    if not dry_run:
        plan.save()

    return plan


def _get_or_create_new_software_plan_version(plan, from_version, new_role, dry_run=False):
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    version = plan.get_version()
    if version and version.role.slug == new_role.slug:
        logger.info(
            f'{dry_run_tag}Found software plan version for plan {plan.name} with role {new_role.slug}.'
        )
        return version
    else:
        new_version = SoftwarePlanVersion(
            plan=plan,
            product_rate=from_version.product_rate,
            role=new_role,
        )
        if not dry_run:
            new_version.save()
            new_version.feature_rates.set(list(from_version.feature_rates.all()))
            new_version.save()

        logger.info(
            f'{dry_run_tag}Created new software plan version for plan {plan.name} with role {new_role.slug}.'
        )
        return new_version


def _get_or_create_role_with_privilege(existing_role_slug, privilege_slug, dry_run=False):
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    existing_role = Role.objects.get(slug=existing_role_slug)
    new_role_slug = existing_role.slug + NEW_ROLE_SLUG_SUFFIX
    new_role_name = existing_role.name + NEW_NAME_SUFFIX
    # search for legacied version of role
    privilege_role = Role.objects.get(slug=privilege_slug)
    new_role = None
    try:
        new_role = _get_existing_role_with_privilege(new_role_slug, privilege_role)
    except RoleMissingPrivilege:
        logger.error(f'{dry_run_tag}Could not find Grant for {new_role_slug} and {privilege_slug}')
        return None
    except ExistingRoleNotFound:
        new_role = _create_new_role_from_role(
            existing_role, new_role_slug, new_role_name, privilege_role, dry_run=dry_run
        )
    else:
        logger.info(f'{dry_run_tag}Found existing role for {new_role.slug}.')

    return new_role


def _get_existing_role_with_privilege(role_slug, privilege_role):
    """
    :param role_slug: str
    :param privilege_role: Role object
    :return:
    """
    try:
        new_role = Role.objects.get(slug=role_slug)
    except Role.DoesNotExist:
        raise ExistingRoleNotFound
    # ensure grant exists on new role
    try:
        Grant.objects.get(from_role=new_role, to_role=privilege_role)
    except Grant.DoesNotExist:
        raise RoleMissingPrivilege
    return new_role


def _create_new_role_from_role(from_role, new_role_slug, new_role_name, privilege_to_add, dry_run=False):
    """
    :param from_role: Role object of existing role to copy
    :param new_role_slug: str object that is new slug (unique)
    :param new_role_name: str object that is new name
    :param privilege_to_add: Role object of privilege to add to new role via Grant
    :return: new role object
    """
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    new_role = Role(slug=new_role_slug, name=new_role_name)
    if not dry_run:
        new_role.save()
        _copy_existing_grants(from_role, new_role)
        # add new grant
        Grant.objects.create(from_role=new_role, to_role=privilege_to_add)
    logger.info(f"""
    {dry_run_tag}Created new role {new_role.slug} from existing role {from_role.slug} with privilege
    {privilege_to_add.slug}.
    """)
    return new_role


def _copy_existing_grants(copy_from_role, copy_to_role):
    """
    :param copy_from_role: Role object
    :param copy_to_role: Role object
    :return:
    """
    for grant in Grant.objects.filter(from_role=copy_from_role):
        Grant.objects.create(from_role=copy_to_role, to_role=grant.to_role)
