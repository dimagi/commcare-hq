import sys

from django.core.management import BaseCommand

from corehq.apps.hqadmin.service_checks import (
    CHECKS,
    UnknownCheckException,
    run_checks,
)


class Command(BaseCommand):
    help = ("Check the status of various services. "
            "You can check a particular service by passing in it's name.")

    def add_arguments(self, parser):
        parser.add_argument(
            'service_name',
            nargs='?',
            choices=list(CHECKS)
        )

    def handle(self, service_name, **options):
        checks_to_do = [service_name] if service_name else list(CHECKS)

        try:
            statuses = run_checks(checks_to_do)
        except UnknownCheckException:
            print("Services available are:")
            for service_name in CHECKS.keys():
                print("- {}".format(service_name))

            sys.exit(-1)
        else:
            self.print_results(statuses)
            if not all(status[1].success for status in statuses):
                sys.exit(1)

    @staticmethod
    def print_results(results):
        for service_name, status in results:
            if status.exception:
                print("\033[91mEXCEPTION\033[0m (Took {:6.2f}s) {:15}:".format(
                    status.duration,
                    service_name,
                ), end=' ')
                print("Service check errored with exception '{}'".format(repr(status.exception)))
            else:
                print("\033[92mSUCCESS\033[0m" if status.success else "\033[91mFAILURE\033[0m", end=' ')
                print("(Took {:6.2f}s) {:15}: {}".format(status.duration, service_name, status.msg))
