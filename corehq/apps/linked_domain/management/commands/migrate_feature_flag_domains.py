import logging
from collections import defaultdict

from django.core.management import BaseCommand

from django_prbac.models import Grant, Role

from corehq import toggles
from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    change_role_for_software_plan_version,
)
from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanVersion,
    Subscription,
)

logger = logging.getLogger(__name__)

NEW_ROLE_SLUG_SUFFIX = "_erm"
NEW_ROLE_NAME_SUFFIX = " (With ERM)"


class RoleMissingPrivilege(Exception):
    pass


class ExistingRoleNotFound(Exception):
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
        roles_to_update, versions_to_update, versions_to_increment = _get_erm_migration_stats()
        erm_slug = 'release_management'
        _update_roles_in_place(roles_to_update, erm_slug, dry_run=dry_run)
        _update_versions_in_place(versions_to_update, erm_slug, dry_run=dry_run)
        _create_and_migrate_plan_versions_to_new_roles(versions_to_increment, erm_slug, dry_run=dry_run)


def _get_erm_migration_stats():
    active_plan_versions = SoftwarePlanVersion.objects.filter(is_active=True)
    # roles referenced by active software plans as a set (remove duplicates)
    roles = {version.role for version in active_plan_versions}
    roles_to_update_in_place = []
    versions_to_update_in_place = []
    versions_to_increment = {}
    count = 0
    release_management_role = Role.objects.get(slug='release_management')
    # 1) update role in place
    # 2) create new role and update software plan version in place to reference new role
    # 3) create new role and create new software plan version to reference new role
    for role in roles:
        print(f'Processing {count} of {len(roles)} roles')
        count += 1

        # skip roles that already have release management
        if Grant.objects.filter(from_role=role, to_role=release_management_role).exists():
            continue

        # a bit hacky, but these plans are handled in a separate migration
        if role.slug == 'enterprise_plan_v0' or role.slug == 'enterprise_plan_v1':
            continue

        # get all active software plan versions that reference this role
        versions = SoftwarePlanVersion.objects.filter(role=role, is_active=True)

        # get all subscriptions associated with this software plan version
        subscriptions = [
            subscription for version in versions for subscription in Subscription.visible_objects.filter(
                plan_version=version, is_active=True
            )
        ]
        domains = [sub.subscriber.domain for sub in subscriptions]
        domains_for_software_plan_version_id = defaultdict(list)
        toggle_enabled = [toggles.LINKED_DOMAINS.enabled(domain) for domain in domains]
        if len(set(toggle_enabled)) == 1 and toggle_enabled[0]:
            # all domains that reference this role via all possible plan versions have the feature flag enabled
            # this is (1) update role in place
            roles_to_update_in_place.append(role.slug)
            continue

        # not all domains have feature flag enabled, need to do more investigation
        for version in versions:
            subscriptions = Subscription.visible_objects.filter(plan_version=version, is_active=True)
            domains_for_subscriptions = [subscription.subscriber.domain for subscription in subscriptions]
            domains_for_software_plan_version_id[version.id].extend(domains_for_subscriptions)

        for plan_version_id, domains in domains_for_software_plan_version_id.items():
            toggle_enabled = [toggles.LINKED_DOMAINS.enabled(domain) for domain in domains]
            if len(set(toggle_enabled)) == 1 and toggle_enabled[0]:
                # all domains referencing this software plan version have the feature flag enabled
                # this is (2) update version in place
                versions_to_update_in_place.append(plan_version_id)
            elif len(set(toggle_enabled)) == 2:
                # not all domains referencing this software plan version have feature flag enabled
                # this is (3) mark which plan_id/domain need to be updated
                # add domains that should be updated to the new role
                versions_to_increment[plan_version_id] = [
                    domain for domain in domains if toggles.LINKED_DOMAINS.enabled(domain)
                ]

    return roles_to_update_in_place, versions_to_update_in_place, versions_to_increment


def _update_roles_in_place(role_slugs, privilege_slug, dry_run=False):
    for role_slug in role_slugs:
        role = Role.objects.get(slug=role_slug)
        role_for_privilege = Role.objects.get(slug=privilege_slug)
        if not dry_run:
            Grant.objects.create(from_role=role, to_role=role_for_privilege)
        logger.info(f'Added {privilege_slug} privilege to {role.slug}.')


def _update_versions_in_place(version_ids, privilege_slug, dry_run=False):
    for version_id in version_ids:
        version = SoftwarePlanVersion.objects.get(id=version_id)
        new_role = _get_or_create_role_with_privilege(version.role.slug, privilege_slug, dry_run=dry_run)
        if new_role:
            change_role_for_software_plan_version(
                version.role.slug, new_role.slug, limit_to_plan_version_id=version_id
            )


def _create_and_migrate_plan_versions_to_new_roles(domains_by_version_id, privilege_slug, dry_run=False):
    """
    :param domains_by_version_id: {plan_id: [domains], ...}
    :param privilege_slug:
    :param dry_run:
    :return:
    """
    for plan_id, domains in domains_by_version_id:
        # create a new software plan version for this subscription
        current_version = SoftwarePlanVersion.objects.get(id=plan_id)
        new_role = _get_or_create_role_with_privilege(current_version.role.slug, privilege_slug, dry_run=dry_run)
        new_version = _create_new_plan_version_from_version(current_version, new_role)
        if new_role and new_version:
            for domain in domains:
                subscription = Subscription.get_active_subscription_by_domain(domain)
                # TODO: do I need to use the more formal upgrade_subscriptions_to_latest_plan_version?
                subscription.plan_version = new_version
                subscription.save()


def _create_new_plan_version_from_version(from_version, role_with_privilege, dry_run=False):
    new_version = SoftwarePlanVersion(
        plan=from_version.plan,
        product_rate=from_version.product_rate,
        role=role_with_privilege,
    )
    if not dry_run:
        new_version.save()
        new_version.feature_rates.set(list(from_version.feature_rates.all()))
        new_version.save()
        return new_version

    return None


def _get_or_create_role_with_privilege(existing_role_slug, privilege_slug, dry_run=False):
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    existing_role = Role.objects.get(slug=existing_role_slug)
    new_role_slug = existing_role.slug + NEW_ROLE_SLUG_SUFFIX
    new_role_name = existing_role.name + NEW_ROLE_NAME_SUFFIX
    # search for legacied version of role
    privilege_role = Role.objects.get(slug=privilege_slug)
    new_role = None
    try:
        new_role = _get_existing_role_with_privilege(new_role_slug, privilege_role)
    except RoleMissingPrivilege:
        logger.error(f'{dry_run_tag}Could not find Grant for {new_role_slug} and {privilege_slug}')
        return None
    except ExistingRoleNotFound:
        if not dry_run:
            new_role = _create_new_role_from_role(existing_role, new_role_slug, new_role_name, privilege_role)
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


def _create_new_role_from_role(from_role, new_role_slug, new_role_name, privilege_to_add):
    """
    :param from_role: Role object of existing role to copy
    :param new_role_slug: str object that is new slug (unique)
    :param new_role_name: str object that is new name
    :param privilege_to_add: Role object of privilege to add to new role via Grant
    :return: new role object
    """
    new_role = Role(slug=new_role_slug, name=new_role_name)
    new_role.save()
    _copy_existing_grants(from_role, new_role)
    # add new grant
    Grant.objects.create(from_role=new_role, to_role=privilege_to_add)
    return new_role


def _copy_existing_grants(copy_from_role, copy_to_role):
    """
    :param copy_from_role: Role object
    :param copy_to_role: Role object
    :return:
    """
    for grant in Grant.objects.filter(from_role=copy_from_role):
        Grant.objects.create(from_role=copy_to_role, to_role=grant.to_role)
