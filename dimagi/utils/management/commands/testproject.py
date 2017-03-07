from __future__ import print_function
from django.core.management import call_command
from django.core.management.base import BaseCommand
import settings


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--xmlreporting',
            action='store_true',
            dest='xml_reporting',
            default=False,
            help='Use xml reporting for build server integration (default=False)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            dest='test_all',
            default=False,
            help='Test ALL apps in project. (default=False)',
        )

    help = "Test only the relevant apps as defined in the settings file for your project.  Ignore django standard and other third party apps."
    label = "Test a subset of the apps for your project"

    def handle(self, **options):
        xmlreporting = options.get('xml_reporting', False)
        test_all = options.get('test_all', False)

        if xmlreporting:
            settings.TEST_RUNNER = 'xmlrunner.extra.djangotestrunner.run_tests'
            settings.TEST_OUTPUT_VERBOSE = True
            settings.TEST_OUTPUT_DESCRIPTIONS = True
            settings.TEST_OUTPUT_DIR = 'xmlrunner'

        if test_all:
            call_command('test')
        else:
            args = ['test'] + settings.DEV_APPS
            print(args)

            call_command(*args)
