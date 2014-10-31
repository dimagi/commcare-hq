from django.core.management.base import BaseCommand
from corehq.apps.commtrack.models import Program
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.util import get_or_create_default_program


class Command(BaseCommand):
    help = 'Populate default program flag for domains'

    def handle(self, *args, **options):
        self.stdout.write("Fixing default programs...\n")

        for domain in Domain.get_all():
            if not domain.commtrack_enabled:
                continue

            if Program.default_for_domain(domain.name):
                continue

            programs = Program.by_domain(domain.name)

            # filter anything named 'default' or 'Default'
            current_default = [
                p for p in programs
                if p.name == 'Default' or p.name == 'default'
            ]

            # if they never changed their default programs
            # name, we don't want to add a confusing new one
            # so just flip this to the default
            if len(current_default) == 1:
                p.default = True
                p.save()
            else:
                get_or_create_default_program(domain.name)
