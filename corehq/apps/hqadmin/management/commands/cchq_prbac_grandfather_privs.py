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

        skipped_editions = []
        if skip_edition:
            skipped_editions = skip_edition.split(',')
            if not _confirm_community_deprecated(skipped_editions, noinput=noinput):
                return

            query = query.exclude(plan__edition__in=skipped_editions)

        all_role_slugs = set(
            query.distinct('role__slug').values_list('role__slug', flat=True)
        )
        all_plan_slugs = (
            all_role_slugs
            - set(MAX_PRIVILEGES)  # no privileges should be in software plan roles, this is just a safeguard
            - set(plan_slug.strip() for plan_slug in kwargs.get('skip', '').split(','))
        )

        # make sure that these roles are not attached to SoftwarePlanEditions
        # that they aren't meant to be attached to. e.g. the pro_plan_v1 role
        # attached to a SoftwarePlanVersion under the Advanced edition.
        # see https://dimagi-dev.atlassian.net/browse/SAASP-10124
        all_plan_slugs = [
            plan_slug for plan_slug in all_plan_slugs if _get_role_edition(plan_slug) not in skipped_editions
        ]

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


def _confirm_community_deprecated(skipped_editions, noinput=False):
    mismatched_edition = 'Community' in skipped_editions and 'Free' not in skipped_editions
    if mismatched_edition and not noinput:
        community_deprecated_msg = (
            "Community Edition was changed to Free Edition in April 2025.\n"
            "You should probably replace 'Community' with 'Free', or include both to be on the safe side."
            "\nProceed anyway?"
        )
        return _confirm(community_deprecated_msg)
    if mismatched_edition and noinput:
        message = "Warning: The 'Community' edition is deprecated. Using 'Free' edition instead."
        print(f"\033[1m\033[93m{message}\033[0m")
        skipped_editions.remove('Community')
        skipped_editions.append('Free')
    return True


def _confirm(msg):
    confirm_update = input(msg + ' [y/N] ')
    if not confirm_update:
        return False
    return confirm_update.lower() == 'y'


def _get_role_edition(role_slug):
    all_editions = SoftwarePlanVersion.objects.filter(
        role__slug=role_slug).distinct(
        'plan__edition').values_list('plan__edition', flat=True)

    if len(all_editions) == 1:
        return all_editions[0]

    def _count_edition(edition):
        return SoftwarePlanVersion.objects.filter(
            role__slug=role_slug, plan__edition=edition).count()

    return max(all_editions, key=_count_edition)
