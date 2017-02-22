from __future__ import print_function
from corehq.apps.sms.models import PhoneNumber
from django.core.management.base import BaseCommand
from optparse import make_option


class Command(BaseCommand):
    args = ""
    help = "Adds couch_id to PhoneNumbers missing it"
    option_list = BaseCommand.option_list + (
        make_option("--check",
                    action="store_true",
                    dest="check",
                    default=False,
                    help="Include this option to only check the number of PhoneNumbers missing couch_id."),
    )

    def get_queryset(self):
        return PhoneNumber.objects.filter(couch_id__isnull=True)

    def show_missing_count(self):
        count = self.get_queryset().count()
        print("There are %s PhoneNumbers missing couch_id" % count)

    def apply_fix(self):
        print("Applying fix...")
        for phone_number in self.get_queryset():
            phone_number.save()

    def handle(self, *args, **options):
        if not options['check']:
            self.show_missing_count()
            self.apply_fix()

        self.show_missing_count()
