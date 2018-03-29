from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.hqadmin.service_checks import CHECKS, run_checks


class Command(BaseCommand):
    help = ("Check the status of various services. "
            "You can check a particular service by passing in it's name.")

    def add_arguments(self, parser):
        parser.add_argument(
            'service_name',
            nargs='?',
        )

    def handle(self, service_name, **options):
        checks_to_do = []
        if service_name:
            if service_name not in CHECKS:
                print("Services available are:")
                for service_name in CHECKS.keys():
                    print("- {}".format(service_name))
                return
            else:
                service_check = CHECKS[service_name]
                checks_to_do.append((service_name, service_check))
        else:
            checks_to_do = CHECKS.items()

        statuses = run_checks(checks_to_do)
        self.print_results(statuses)

    @staticmethod
    def print_results(results):
        for service_name, status in results:
            if status.exception:
                print("\033[91mEXCEPTION\033[0m {}: Service check errored with exception '{}'".format(
                    service_name,
                    repr(status.exception)
                ))
            else:
                print("\033[92mSUCCESS\033[0m" if status.success else "\033[91mFAILURE\033[0m", end=' ')
                print("{}: {}".format(service_name, status.msg))
