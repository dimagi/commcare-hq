from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from couchforms.dbaccessors import get_forms_in_date_range
from couchforms.models import XFormInstance
from dimagi.utils.parsing import string_to_datetime, json_format_datetime

class Command(BaseCommand):
    args = "<domain xmlns from_date to_date>"
    help = "Delete duplicate form submissions."

    def delete_dup_forms(self, domain, xmlns, from_date, to_date):
        forms = get_forms_in_date_range(domain, from_date, to_date)
        keys = {}
        for form in forms:
            form_inst = form.form
            if form_inst.get("@xmlns") == xmlns:
                # Timestamp of device event: ddmmyyhhmmss
                t = form_inst.get("t")
                # Serial number of device
                sn = form_inst.get("sn")
                if t and sn:
                    key = "%s_%s" % (sn, t)
                    if key in keys:
                        print "Deleting form id %s" % form._id
                        form.doc_type += "-Deleted"
                        form.save()
                    else:
                        keys[key] = True

    def validate_date(self, date):
        try:
            date_test = json_format_datetime(string_to_datetime(date))
        except Exception:
            date_test = None
        if date_test is None or date != date_test:
            raise CommandError("Invalid datetime given for argument '%s'. Argument must be json-formatted." % date)

    def validate_args(self, *args):
        if len(args) < 4:
            raise CommandError("Usage: python manage.py delete_duplicate_device_events <domain xmlns from_date to_date>")
        self.validate_date(args[2])
        self.validate_date(args[3])

    def handle(self, *args, **options):
        self.validate_args(*args)
        self.delete_dup_forms(args[0], args[1], args[2], args[3])

