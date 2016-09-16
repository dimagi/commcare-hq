from optparse import make_option

from django.core.management.base import BaseCommand

from corehq.privileges import MAX_PRIVILEGES
from corehq.apps.accounting.utils import ensure_grant
from corehq.apps.accounting.models import Role


class Command(BaseCommand):
    help = 'Grandfather privileges to all roles above a certain plan level and custom roles'

    option_list = BaseCommand.option_list + (
        make_option(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what would happen'
        ),
        make_option(
            '--noinput',
            action='store_true',
            default=False,
            help='Whether to skip confirmation dialogs'
        ),
        make_option(
            "-s",
            "--skip",
            dest="skip",
            help="A comma separated list of plan roles to skip if any",
        ),
        make_option(
            "--verbose",
            dest="verbose",
            help="Verbose logging",
            default=True,
        )
    )

    def handle(self, *privs, **kwargs):

        dry_run = kwargs.get('dry_run', False)
        verbose = kwargs.get('verbose')
        noinput = kwargs.get('noinput')
        all_plan_slugs = (
            set(map(lambda role: role.slug, Role.objects.all())) -
            set(MAX_PRIVILEGES) -
            set(map(lambda plan_slug: plan_slug.strip(), kwargs.get('skip', []).split(',')))
        )

        if not dry_run and not noinput and not _confirm('Are you sure you want to grant {} to {}?'.format(
                ', '.join(privs),
                ', '.join(all_plan_slugs),
        )):
            print 'Aborting'
            return

        if not all(map(lambda priv: priv in MAX_PRIVILEGES, privs)):
            print 'Not all specified privileges are valid: {}'.format(', '.join(privs))
            return

        for plan_role_slug in all_plan_slugs:
            for priv in privs:
                ensure_grant(plan_role_slug, priv, dry_run=dry_run, verbose=verbose)


def _confirm(msg):
    confirm_update = raw_input(msg + ' [y/N] ')
    if not confirm_update:
        return False
    return confirm_update.lower() == 'y'
