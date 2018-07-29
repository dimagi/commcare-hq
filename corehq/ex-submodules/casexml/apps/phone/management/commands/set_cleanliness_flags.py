from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand


class Command(BaseCommand):
    """
    Set cleanliness flags for a domain, or for all domains
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            nargs='?',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help="Force rebuild on top of existing flags/hints.",
        )

    def handle(self, domain, **options):
        from casexml.apps.phone.cleanliness import (
            set_cleanliness_flags_for_domain, set_cleanliness_flags_for_all_domains)
        force_full = options['force']
        if domain:
            set_cleanliness_flags_for_domain(domain, force_full=force_full)
        else:
            set_cleanliness_flags_for_all_domains(force_full=force_full)
