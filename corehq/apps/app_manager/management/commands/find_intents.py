from django.core.management import BaseCommand
from corehq.apps.domain.models import Domain
import csv
import sys


class Command(BaseCommand):
    def handle(self, *args, **options):
        csvWriter = csv.writer(sys.stdout)
        for domain in Domain.get_all():
            for app in domain.full_applications(include_builds=False):
                for module in app.modules:
                    for form in module.forms:
                        intents = form.wrapped_xform().odk_intents
                        if len(intents):
                            csvWriter.writerow([domain.name, app.name,
                                               module.name, form.name, intents])
