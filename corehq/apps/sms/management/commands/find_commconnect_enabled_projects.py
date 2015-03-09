from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    args = ""
    help = ""

    def handle(self, *args, **options):
        for domain in Domain.get_all():
            if domain.commconnect_enabled:
                print "%s has commconnect_enabled=True" % domain.name
