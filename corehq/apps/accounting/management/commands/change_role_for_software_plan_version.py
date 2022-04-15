import logging

from django.core.management import BaseCommand

from django_prbac.models import Role

from corehq.apps.accounting.models import SoftwarePlanVersion

logger = logging.getLogger(__name__)


class OldRoleDoesNotExist(Exception):
    pass


class NewRoleDoesNotExist(Exception):
    pass


class PlanVersionAndRoleMismatch(Exception):
    pass


def change_role_for_software_plan_version(old_role, new_role, limit_to_plan_version_id=None, dry_run=False):
    """
    We typically do not support modifying SoftwarePlanVersions directly, and instead encourage creating a new one.
    This command should only be used when it seems appropriate. The most typical use case would be when it is
    desirable to delete the Role(slug=old_role) object entirely, and using this command to ensure no software
    plan versions reference that old role.
    :param old_role: slug for role to search for
    :param new_role: slug for role that new software plan version should reference
    :param limit_to_plan_version_id: limit change to a specific plan version id
    :param dry_run: if False, will make changes to the DB
    :return: a list of plan names that were modified
    """
    dry_run_tag = '[DRY_RUN]' if dry_run else ''

    if not Role.objects.filter(slug=old_role).exists():
        raise OldRoleDoesNotExist

    try:
        new_role_obj = Role.objects.get(slug=new_role)
    except Role.DoesNotExist:
        raise NewRoleDoesNotExist

    if limit_to_plan_version_id:
        version = SoftwarePlanVersion.objects.get(id=limit_to_plan_version_id)
        if version.role.slug != old_role:
            raise PlanVersionAndRoleMismatch
        versions = [version]
    else:
        versions = SoftwarePlanVersion.objects.filter(role__slug=old_role)

    changed_plans = set()
    for software_plan_version in versions:
        if not dry_run:
            software_plan_version.role = new_role_obj
            software_plan_version.save()

        changed_plans.add(software_plan_version.plan.name)
        logger.info(f"{dry_run_tag}Changed the {software_plan_version.plan.name} software plan's role from"
                    f" {old_role} to {new_role}.")

    return list(changed_plans)


class Command(BaseCommand):
    help = 'Modify existing software plan versions to reference a new role. Use wisely.'

    def add_arguments(self, parser):
        parser.add_argument('old_role')
        parser.add_argument('new_role')
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--quiet', action="store_true", default=False)

    def handle(self, old_role, new_role, **kwargs):
        logger.setLevel(logging.WARNING if kwargs.get('quiet') else logging.INFO)
        try:
            changed_plans = change_role_for_software_plan_version(
                old_role,
                new_role,
                dry_run=kwargs.get('dry_run'),
            )
        except OldRoleDoesNotExist:
            logger.error(f"Old role slug {old_role} does not exist.")
        except NewRoleDoesNotExist:
            logger.error(f"New role slug {new_role} does not exist.")
        else:
            formatted_plans = "\n".join(changed_plans)
            logger.info(f"Successfully modified the following plans:\n{formatted_plans}")
