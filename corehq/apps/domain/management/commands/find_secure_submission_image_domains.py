from __future__ import absolute_import
from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
import csv


class Command(BaseCommand):
    help = 'Find domains with secure submissions and image questions'

    def check_domain(self, domain, csv_writer):
        if domain.secure_submissions:
            for app in domain.full_applications(include_builds=False):
                for module in app.modules:
                    for form in module.forms:
                        for question in form.get_questions(app.langs):
                            if question['type'] in ('Image', 'Audio', 'Video'):
                                csv_writer.writerow([
                                    domain.name,
                                    app.name,
                                    domain.creating_user
                                ])
                                return

    def handle(self, **options):
        with open('domain_results.csv', 'wb+') as csvfile:
            csv_writer = csv.writer(
                csvfile,
                delimiter=',',
                quotechar='|',
                quoting=csv.QUOTE_MINIMAL
            )

            csv_writer.writerow(['domain', 'app', 'domain_creator'])

            for domain in Domain.get_all(include_docs=True):
                self.check_domain(domain, csv_writer)
