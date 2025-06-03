import json
from pathlib import Path

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.exceptions import AppValidationError
from corehq.apps.app_manager.models import import_app
from corehq.apps.data_cleaning.management.commands.utils import input_validation

APP_JSON_DIR = Path(__file__).resolve().parent / 'utils' / 'apps'


def get_plant_app_template():
    with open(APP_JSON_DIR / 'plant_care_app.json') as f:
        return json.load(f)


class Command(BaseCommand):
    help = (
        f'Creates a copy of the {input_validation.DATA_CLEANING_TEST_APP_NAME} '
        f'app for generating fake data for the data cleaning tool.'
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        is_real_domain = input_validation.is_real_domain(domain)
        if not is_real_domain:
            self.stderr.write(input_validation.get_domain_missing_error(domain))
            return
        existing_app = input_validation.get_fake_app(domain)
        if existing_app:
            self.stderr.write(
                f"Domain {domain} already has the '{input_validation.DATA_CLEANING_TEST_APP_NAME} app."
            )
            return
        template = get_plant_app_template()
        app = import_app(
            template,
            domain,
            {
                'created_from_template': 'plant_care_app',
            },
        )
        app.name = input_validation.DATA_CLEANING_TEST_APP_NAME
        try:
            app_copy = app.make_build(comment='This is for generating fake data for the data cleaning tool.')
        except AppValidationError as e:
            self.stderr.write(f'Error creating build for Plant Care: {e}')
            return
        app_copy.is_released = True
        app_copy.save(increment_version=False)
        self.stdout.write(f'Created app {app_copy.id} for domain {domain}.')
