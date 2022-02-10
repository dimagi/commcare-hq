import logging

from django.core.management import BaseCommand

from django_prbac.models import Grant, Role

from corehq import toggles
from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    change_role_for_software_plan_version,
)
from corehq.apps.accounting.models import (
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    Subscription,
)
from corehq.apps.domain.models import Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Enables the RELEASE_MANAGEMENT privilege on any domain that has the Linked Projects feature flag enabled
    """

    def add_arguments(self, parser):
        parser.add_argument('-q', '--quiet', help="Quiet output to warnings/errors only")
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, quiet, dry_run, **options):
        logger.setLevel(logging.WARNING if quiet else logging.INFO)
        automatic_upgrades, manual_upgrades = _find_plans_with_linked_projects_toggle()
        _upgrade_plans(automatic_upgrades, dry_run=dry_run)
        logger.info('The following plans need to be manually audited to determine if they are eligible for ERM.')
        formatted_manual_info = "\n".join(manual_upgrades)
        logger.info(formatted_manual_info)


def _find_plans_with_linked_projects_toggle():
    manual_audits = []
    automated_upgrades = []
    for domain in toggles.LINKED_DOMAINS.get_enabled_domains():
        domain_obj = Domain.get_by_name(domain)
        if not domain_obj:
            continue
        if domain_obj.is_test == 'true':
            continue
        subscription = Subscription.get_active_subscription_by_domain(domain)
        plan_version = subscription.plan_version if subscription else \
            Subscription.get_subscribed_plan_by_domain(domain)
        if plan_version.role.slug not in ['enterprise_plan_v0', 'enterprise_plan_v1']:
            is_public = plan_version.plan.visibility == SoftwarePlanVisibility.PUBLIC
            is_community = plan_version.plan.edition == SoftwarePlanEdition.COMMUNITY
            entry = {
                'domain': domain,
                'plan': plan_version.plan.name,
                'role_slug': plan_version.role.slug,
                'role_name': plan_version.role.name,
                'edition': plan_version.plan.edition,
                'visibility': plan_version.plan.visibility,
                'active_subscription': subscription is not None,
                'created_by': domain_obj.creating_user,
            }
            if is_public or is_community:
                manual_audits.append(entry)
            else:
                automated_upgrades.append(entry)

    return automated_upgrades, manual_audits


def _upgrade_plans(automatic_upgrades, dry_run=False):
    slug_suffix = '_with_erm'
    name_suffix = '(With ERM)'
    for plan_info in automatic_upgrades:
        new_role = _get_or_create_role(plan_info['role_slug'], slug_suffix, name_suffix, dry_run=dry_run)
        change_role_for_software_plan_version(plan_info['role_slug'], new_role.slug, dry_run=dry_run)


def _get_or_create_role(existing_role_slug, slug_suffix, name_suffix, dry_run=False):
    dry_run_tag = '[DRY_RUN]' if dry_run else ''
    existing_role = Role.objects.get(slug=existing_role_slug)
    new_role_slug = existing_role.slug + slug_suffix
    new_role_name = existing_role.name + name_suffix
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
