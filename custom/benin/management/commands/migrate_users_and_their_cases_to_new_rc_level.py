from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Migrate benin project\'s users and their cases to new rc level locations'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('domain')
        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            help="A dry run to only share the updates that would happen",
        )

    def handle(self, domain, **options):
        """
        Steps:
        1. Fetch all villages (location type: Village).
        2. For each village:
            1. Fetch all users assigned to the village with usertype 'rc'
            2. For each user
                1. find the corresponding RC under the village with name same as user's user data in rc_number.
                   Log error if no matching RC, and move to next user
                2. if RC present
                    1. Find all OPEN cases (case_type: menage, membre)
                        1. owned by village
                        2. opened_by the user (Use CaseES.opened_by)
                    2. Find all OPEN cases (case_type: seance_educative, fiche_pointage)
                        1. opened_by the user (Use CaseES.opened_by)
                        2. Why are we updating it though? They are already owned by users. They aren't many though
                    3. Update all cases
                        1. Update owner to be the corresponding RC location
                    4. Update users location to corresponding RC location
        """
        pass
