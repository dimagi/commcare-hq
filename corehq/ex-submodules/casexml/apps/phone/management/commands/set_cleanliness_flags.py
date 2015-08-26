from optparse import make_option
from django.core.management import BaseCommand


class Command(BaseCommand):
    """
    Set cleanliness flags for a domain, or for all domains
    """
    option_list = BaseCommand.option_list + (
        make_option('--force',
                    action='store_true',
                    dest='force',
                    default=False,
                    help="Force rebuild on top of existing flags/hints."),
    )

    def handle(self, *args, **options):
        from casexml.apps.phone.cleanliness import (
            set_cleanliness_flags_for_domain, set_cleanliness_flags_for_enabled_domains)
        force_full = options['force']
        if len(args) == 1:
            domain = args[0]
            set_cleanliness_flags_for_domain(domain, force_full=force_full)
        else:
            assert len(args) == 0
            set_cleanliness_flags_for_enabled_domains(force_full=force_full)
