import logging

from django.core.management.base import BaseCommand
from django_prbac.models import Role

from corehq.apps.accounting.models import SoftwarePlanVersion
from corehq.apps.accounting.utils import revoke_privs_for_grantees
from corehq.apps.hqadmin.management.commands.cchq_prbac_grandfather_privs import _confirm, _get_role_edition
from corehq.privileges import MAX_PRIVILEGES

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Revoke privileges'

    def handle(self, privs, **kwargs):
        dry_run = kwargs.get('dry_run')
        verbose = kwargs.get('verbose')
        noinput = kwargs.get('noinput')
        skip_edition = kwargs.get('skip_edition')
        delete_revoked_privs = kwargs.get('delete_privs')
        check_privs_exist = kwargs.get('check_privs_exist')

        logger.setLevel(logging.INFO if verbose else logging.WARNING)
        dry_run_tag = "[DRY RUN] " if dry_run else ""

        query = SoftwarePlanVersion.objects

        skipped_editions = []
        if skip_edition:
            skipped_editions = skip_edition.split(',')
            query = query.exclude(plan__edition__in=skipped_editions)

        all_role_slugs = set(
            query.distinct('role__slug').values_list('role__slug', flat=True)
        )
        all_plan_slugs = (
            all_role_slugs -
            set(MAX_PRIVILEGES) -  # no privileges should be in software plan roles, this is just a safeguard
            set(plan_slug.strip() for plan_slug in kwargs.get('skip', '').split(','))
        )

        # make sure that these roles are not attached to SoftwarePlanEditions
        # that they aren't meant to be attached to. e.g. thw pro_plan_v1 role
        # attached to a SoftwarePlanVersion under the Advanced edition.
        # see https://dimagi-dev.atlassian.net/browse/SAASP-10124
        all_plan_slugs = [
            plan_slug for plan_slug in all_plan_slugs if _get_role_edition(plan_slug) not in skipped_editions
        ]

        if not dry_run and not noinput and not _confirm('Are you sure you want to revoke {} for {}?'.format(
            ', '.join(privs),
            ', '.join(all_plan_slugs),
        )):
            logger.error('Aborting')
            return

        if check_privs_exist and not all(priv in MAX_PRIVILEGES for priv in privs):
            logger.error('Not all specified privileges are valid: {}'.format(', '.join(privs)))
            return

        privs_to_revoke = ((role_slug, privs) for role_slug in all_plan_slugs)
        revoke_privs_for_grantees(privs_to_revoke, dry_run=dry_run, verbose=verbose)
        if delete_revoked_privs:
            if skipped_editions:
                logger.error(
                    "Cannot safely delete revoked privileges until ensuring they have been revoked for all "
                    "editions. If you are sure you want to delete the privilege, run again without specifying any "
                    "skipped editions."
                )
                return
            for priv in privs:
                try:
                    role_to_delete = Role.objects.get(slug=priv)
                    if not dry_run:
                        role_to_delete.delete()
                except Role.DoesNotExist:
                    logger.warning(f"{dry_run_tag}Role for privilege {priv} does not exist. Nothing to delete.")
                else:
                    logger.info(
                        f"{dry_run_tag}Deleted role for privilege {priv} from database. To ensure the role is not "
                        f"recreated, remove remaining references in the codebase."
                    )

    def add_arguments(self, parser):
        parser.add_argument(
            'privs',
            nargs='+',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what would happen'
        ),
        parser.add_argument(
            '--noinput',
            action='store_true',
            default=False,
            help='Whether to skip confirmation dialogs'
        ),
        parser.add_argument(
            "-s",
            "--skip",
            dest="skip",
            default="",
            help="A comma separated list of plan roles to skip if any",
        ),
        parser.add_argument(
            "--skip-edition",
            dest="skip_edition",
            help="A comma separated list of plan editions to skip if any",
        ),
        parser.add_argument(
            "--verbose",
            action='store_false',
            dest="verbose",
            help="Verbose logging",
            default=True,
        ),
        parser.add_argument(
            '--delete-privs',
            action='store_true',
            default=False,
            help='If privilege has been revoked for all plans, delete the Role object associated with it'
        ),
        parser.add_argument(
            '--check-privs-exist',
            action='store_true',
            default=True,
            help='Ensure all privileges are valid before attempting to revoke.'
        )
