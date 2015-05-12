from django.core.management import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    """
    Set cleanliness flags for a domain, or for all domains
    """

    def handle(self, *args, **kwargs):
        from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_domain
        if len(args) == 1:
            domain = args[0]
            set_cleanliness_flags_for_domain(domain)
        else:
            assert len(args) == 0
            for domain in Domain.get_all_names():
                print 'updating flags for {}'.format(domain)
                set_cleanliness_flags_for_domain(domain)
