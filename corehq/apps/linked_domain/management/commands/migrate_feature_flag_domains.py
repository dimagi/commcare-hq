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
        _update_roles_in_place(roles_to_update_in_place)
        _create_and_migrate_to_new_roles(roles_to_increment)


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


def _update_roles_in_place(role_slugs, dry_run=False):
    for role_slug in role_slugs:
        role = Role.objects.get(slug=role_slug)
        release_management_role = Role.objects.get(slug='release_management')
        if not dry_run:
            Grant.objects.create(from_role=role, to_role=release_management_role)
        logger.info(f'Added release management privilege to {role.slug}.')


def _create_and_migrate_to_new_roles(domains_by_role_slug, dry_run=False):
    for role_slug, domains in domains_by_role_slug:
        new_role = _get_or_create_role(role_slug, dry_run=dry_run)
        for domain in domains:
            subscription = Subscription.get_active_subscription_by_domain(domain)
            change_role_for_software_plan_version(
                role_slug, new_role.slug, limit_to_plan_version_id=subscription.plan_version.id
            )


def _get_or_create_role(existing_role_slug, dry_run=False):
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    existing_role = Role.objects.get(slug=existing_role_slug)
    new_role_slug = existing_role.slug + NEW_ROLE_SLUG_SUFFIX
    new_role_name = existing_role.name + NEW_ROLE_NAME_SUFFIX
    # search for grandfathered version of role
    try:
        new_role = Role.objects.get(slug=new_role_slug)
        logger.info(f'{dry_run_tag}Found existing role for {new_role.slug}.')
    except Role.DoesNotExist:
        release_management_role = Role.objects.get(slug='release_management')
        # copy existing role to new role
        new_role = Role(slug=new_role_slug, name=new_role_name)
        if not dry_run:
            new_role.save()
            _copy_existing_grants(existing_role, new_role)
            # add new grant
            Grant.objects.create(from_role=new_role, to_role=release_management_role)
        logger.info(f'{dry_run_tag}Created new role with slug {new_role_slug}.')
    return new_role


def _copy_existing_grants(copy_from_role, copy_to_role):
    for grant in Grant.objects.filter(from_role=copy_from_role):
        Grant.objects.create(from_role=copy_to_role, to_role=grant.to_role)
