import yaml
from django.core.management.base import BaseCommand

from corehq.apps.app_tester import run_tests


class Command(BaseCommand):
    help = 'Run tests found in the given YAML file'
    args = '<yaml_file>'

    def handle(self, *args, **options):
        yaml_file = args[0]
        test_data = yaml.load(yaml_file)
        run_tests(test_data)
