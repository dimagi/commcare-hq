import csv
import logging
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import LabelCommand
from couchforms.models import XFormInstance


class Command(LabelCommand):
    help = "Archive MVP Forms"
    args = "filepath archiving_user"

    def handle(self, *args, **options):
        if len(args) < 2:
            print "please specify a filepath and an archiving_user"
            return
        filepath = args[0]
        archiving_user = args[1]

        try:
            form_ids = open(filepath)
        except Exception as e:
            print "there was an issue opening the file: %s" % e
            return

        try:
            form_ids = [f[0] for f in csv.reader(form_ids)]
        except Exception as e:
            print "there was an issue reading the file %s" % e
            return

        for xform_doc in iter_docs(XFormInstance.get_db(), form_ids):
            try:
                xform = XFormInstance.wrap(xform_doc)
                xform.archive(user_id=archiving_user)
                print "Archived form %s in domain %s" % (
                    xform._id, xform.domain
                )
            except Exception as e:
                print "Issue archiving XFORM %s for domain %s: %s" % (
                    xform_doc['_id'], xform_doc['domain'], e
                )
