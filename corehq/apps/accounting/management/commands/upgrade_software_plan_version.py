import logging

from django.core.management import BaseCommand

from django_prbac.models import Role

from corehq.apps.accounting.models import SoftwarePlanVersion

logger = logging.getLogger(__name__)


class OldRoleDoesNotExist(Exception):
    pass


class NewRoleDoesNotExist(Exception):
    pass


def upgrade_software_plan_version(old_role, new_role, limit_to_plans=None, dry_run=False):
    """
    :param old_role: slug for role to search for
    :param new_role: slug for role that new software plan version should reference
    :param limit_to_plans: optionally limit to specific plan names
    :param dry_run: if False, will make changes to the DB
    :return: a list of plan names that were upgraded
    """
    dry_run_tag = '[DRY_RUN]' if dry_run else ''

    try:
        Role.objects.get(slug=old_role)
    except Role.DoesNotExist:
        raise OldRoleDoesNotExist

    try:
        new_role_obj = Role.objects.get(slug=new_role)
    except Role.DoesNotExist:
        raise NewRoleDoesNotExist

    versions = SoftwarePlanVersion.objects.filter(role__slug=old_role, is_active=True)
    if limit_to_plans:
        versions = versions.filter(plan__name__in=limit_to_plans)

    upgraded_plans = set()
    for old_version in versions:
        new_version = SoftwarePlanVersion(
            plan=old_version.plan,
            product_rate=old_version.product_rate,
            role=new_role_obj,
        )
        if not dry_run:
            # need to save before setting feature rates
            new_version.save()
            new_version.feature_rates.set(list(old_version.feature_rates.all()))
            new_version.save()
            old_version.is_active = False
            old_version.save()

        upgraded_plans.add(new_version.plan.name)
        logger.info(f"{dry_run_tag}Upgraded the {new_version.plan.name} software plan from {old_role} to "
                    f"{new_role}.")

    return list(upgraded_plans)


class Command(BaseCommand):
    help = 'Create a new software plan version to reference a new role.'

    def add_arguments(self, parser):
        parser.add_argument('old_role')
        parser.add_argument('new_role')
        parser.add_argument(
            "--limit-plan",
            dest="limit_plans",
            help="A comma separated list of plan names to limit search to",
        )
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--verbose', action="store_true", default=False)

    def handle(self, old_role, new_role, **kwargs):
        logger.setLevel(logging.INFO if kwargs.get('verbose') else logging.WARNING)
        limit_to_plans = kwargs.get('limit_plans').split(',') if kwargs.get('limit_plans') else None
        try:
            upgraded_plans = upgrade_software_plan_version(
                old_role,
                new_role,
                limit_to_plans=limit_to_plans,
                dry_run=kwargs.get('dry_run'),
            )
        except OldRoleDoesNotExist:
            logger.error(f"Old role slug {old_role} does not exist.")
        except NewRoleDoesNotExist:
            logger.error(f"New role slug {new_role} does not exist.")
        else:
            formatted_plans = "\n".join(upgraded_plans)
            logger.info(f"Successfully upgraded the following plans:\n{formatted_plans}")
