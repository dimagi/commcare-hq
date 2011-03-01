from django.core.management import call_command
from django.core.management.base import CommandError, BaseCommand
from optparse import make_option
import os
import settings


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
    #       make_option('--file', action='store', dest='file', default=None, help='File to upload REQUIRED', type='string'),
    #       make_option('--url', action='store', dest='url', default=None, help='URL to upload to*', type='string'),
    make_option('--xmlreporting', action='store_true', dest='xml_reporting', default=False,
                help='Use xml reporting for build server integration (default=False)'),
    make_option('--all', action='store_true', dest='test_all', default=False,
                help='Test ALL apps in project. (default=False)'),
    )
    help = "Test only the relevant apps as defined in the settings file for your project.  Ignore django standard and other third party apps."
    args = ''#"[--file <filename> --url <url> [optional --method {curl | python} --chunked --odk]]"
    label = "Test a subset of the apps for your project"

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
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
            print args

            call_command(*args)


