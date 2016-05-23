from django.core.management import BaseCommand
from corehq.apps.hqadmin.service_checks import checks


class Command(BaseCommand):
    help = 'Check the status of various services'

    def handle(self, *args, **options):
        for service_check in checks:
            check_name = service_check.__name__
            try:
                status = service_check()
            except Exception as e:
                print "EXCEPTION Service check '{}' errored with exception '{}'".format(
                    check_name,
                    repr(e)
                )
            else:
                print "SUCCESS" if status.success else "FAILURE",
                print "{}: {}".format(check_name, status.msg)
