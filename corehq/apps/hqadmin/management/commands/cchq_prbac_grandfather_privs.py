from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import SoftwarePlanVersion
from corehq.apps.accounting.utils import ensure_grants
from corehq.privileges import MAX_PRIVILEGES


class Command(BaseCommand):
    help = 'Grandfather privileges to all roles above a certain plan level and custom roles'

    def handle(self, privs, **kwargs):
        dry_run = kwargs.get('dry_run')
        verbose = kwargs.get('verbose')
        noinput = kwargs.get('noinput')
        skip_edition = kwargs.get('skip_edition')

        query = SoftwarePlanVersion.objects

        if skip_edition:
            query = query.exclude(plan__edition__in=skip_edition.split(','))

        all_role_slugs = set(
            query.distinct('role__slug').values_list('role__slug', flat=True)
        )
        all_plan_slugs = (
            all_role_slugs -
            set(MAX_PRIVILEGES) -  # no privileges should be in software plan roles, this is just a safeguard
            set(plan_slug.strip() for plan_slug in kwargs.get('skip', '').split(','))
        )

        if not dry_run and not noinput and not _confirm('Are you sure you want to grant {} to {}?'.format(
                ', '.join(privs),
                ', '.join(all_plan_slugs),
        )):
            print('Aborting')
            return

        if not all(priv in MAX_PRIVILEGES for priv in privs):
            print('Not all specified privileges are valid: {}'.format(', '.join(privs)))
            return

        grants_to_privs = ((role_slug, privs) for role_slug in all_plan_slugs)
        ensure_grants(grants_to_privs, dry_run=dry_run, verbose=verbose)

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
        )


def _confirm(msg):
    confirm_update = input(msg + ' [y/N] ')
    if not confirm_update:
        return False
    return confirm_update.lower() == 'y'
