from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from couchforms.models import XFormInstance
from dimagi.utils.parsing import string_to_datetime, json_format_datetime

class Command(BaseCommand):
    args = "<domain xmlns from_date to_date>"
    help = "Delete duplicate form submissions."

    def delete_dup_forms(self, domain, xmlns, from_date, to_date):
        forms = XFormInstance.view("couchforms/all_submissions_by_domain",
                                   startkey=[domain, "by_date", from_date],
                                   endkey=[domain, "by_date", to_date, {}],
                                   include_docs=True,
                                   reduce=False).all()
        keys = {}
        for form in forms:
            form_inst = form.get_form
            if form_inst["@xmlns"] == xmlns:
                # Timestamp of device event: ddmmyyhhmmss
                t = form_inst["t"] if "t" in form_inst else None
                # Serial number of device
                sn = form_inst["sn"] if "sn" in form_inst else None
                if t and sn:
                    key = "%s_%s" % (sn, t)
                    if key in keys:
                        print "Deleting form id %s" % form._id
                        form.doc_type += "-Deleted"
                        form.save()
                    else:
                        keys[key] = True

    def validate_date(self, date):
        if json_format_datetime(string_to_datetime(date)) != date:
            raise CommandError("Invalid datetime given for argument '%s'. Argument must be json-formatted." %s date)

    def validate_args(self, *args):
        if len(args) < 4:
            raise CommandError("Usage: python manage.py delete_duplicate_device_events <domain xmlns from_date to_date>")
        self.validate_date(args[2])
        self.validate_date(args[3])

    def handle(self, *args, **options):
        self.validate_args(*args)
        self.delete_dup_forms(args[0], args[1], args[2], args[3])

