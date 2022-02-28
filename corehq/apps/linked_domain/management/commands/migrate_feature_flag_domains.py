import logging

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
        roles_to_update_in_place, roles_to_increment = _get_roles_that_need_migration()
        _update_roles_in_place(roles_to_update_in_place, 'release_management')
        _create_and_migrate_to_new_roles(roles_to_increment, 'release_management')


def _get_roles_that_need_migration():
    plans = SoftwarePlan.objects.all()
    active_plans = list(filter(lambda plan: plan.get_version() is not None, plans))
    # roles referenced by active software plans
    roles = [plan.get_version().role for plan in active_plans]
    # for each role, look at all domains that reference that role
    roles_to_update_in_place = []
    roles_to_increment = {}
    count = 0
    release_management_role = Role.objects.get(slug='release_management')
    for role in roles:
        print(f'Processing {count} of {len(roles)} roles')
        count += 1

        # skip roles that already have release management
        if Grant.objects.filter(from_role=role, to_role=release_management_role).exists():
            continue

        # a bit hacky, but these plans are handled in a separate migration
        if role.slug == 'enterprise_plan_v0' or role.slug == 'enterprise_plan_v1':
            continue

        versions = SoftwarePlanVersion.objects.filter(role=role, is_active=True)

        # get all subscriptions associated with this software plan version
        subscriptions = [
            subscription for version in versions for subscription in Subscription.visible_objects.filter(
                plan_version=version, is_active=True
            )
        ]
        domains = [subscription.subscriber.domain for subscription in subscriptions]
        toggle_enabled = [toggles.LINKED_DOMAINS.enabled(domain) for domain in domains]
        if len(set(toggle_enabled)) == 2:
            # add domains that should be updated to the new role
            roles_to_increment[role.slug] = [
                domain for domain in domains if toggles.LINKED_DOMAINS.enabled(domain)
            ]
        elif len(set(toggle_enabled)) == 1 and toggle_enabled[0]:
            # all domains referencing this role after the feature flag enabled
            roles_to_update_in_place.append(role.slug)
    return roles_to_update_in_place, roles_to_increment


def _update_roles_in_place(role_slugs, privilege_slug, dry_run=False):
    for role_slug in role_slugs:
        role = Role.objects.get(slug=role_slug)
        role_for_privilege = Role.objects.get(slug=privilege_slug)
        if not dry_run:
            Grant.objects.create(from_role=role, to_role=role_for_privilege)
        logger.info(f'Added {privilege_slug} privilege to {role.slug}.')


def _create_and_migrate_to_new_roles(domains_by_role_slug, privilege_slug, dry_run=False):
    for role_slug, domains in domains_by_role_slug:
        new_role = _get_or_create_role_with_privilege(role_slug, privilege_slug, dry_run=dry_run)
        if new_role:
            for domain in domains:
                subscription = Subscription.get_active_subscription_by_domain(domain)
                change_role_for_software_plan_version(
                    role_slug, new_role.slug, limit_to_plan_version_id=subscription.plan_version.id
                )


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
