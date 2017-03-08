from __future__ import print_function
from django.core.management import BaseCommand
from corehq.apps.hqadmin.service_checks import CHECKS


class Command(BaseCommand):
    help = ("Check the status of various services. "
            "You can check a particular service by passing in it's name.")
    args = "service"

    def handle(self, *args, **options):
        if len(args) == 1:
            service_name = args[0]
            if service_name not in CHECKS:
                print("Services available are:")
                for service_name in CHECKS.keys():
                    print("- {}".format(service_name))
            else:
                service_check = CHECKS[service_name]
                self.perform_check(service_name, service_check)
        else:
            for service_name, service_check in CHECKS.items():
                self.perform_check(service_name, service_check)

    @staticmethod
    def perform_check(service_name, service_check):
        try:
            status = service_check()
        except Exception as e:
            print("\033[91mEXCEPTION\033[0m {}: Service check '{}' errored with exception '{}'".format(
                service_name,
                service_check.__name__,
                repr(e)
            ))
        else:
            print("\033[92mSUCCESS\033[0m" if status.success else "\033[91mFAILURE\033[0m", end=' ')
            print("{}: {}".format(service_name, status.msg))
