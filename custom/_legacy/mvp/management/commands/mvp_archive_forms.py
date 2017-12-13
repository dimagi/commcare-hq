from __future__ import print_function
from __future__ import absolute_import
import csv
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from couchforms.models import XFormInstance


class Command(BaseCommand):
    help = "Archive MVP Forms"

    def add_arguments(self, parser):
        parser.add_argument('filepath')
        parser.add_argument('archiving_user')

    def handle(self, filepath, archiving_user, **options):
        try:
            form_ids = open(filepath)
        except Exception as e:
            print("there was an issue opening the file: %s" % e)
            return

        try:
            form_ids = [f[0] for f in csv.reader(form_ids)]
        except Exception as e:
            print("there was an issue reading the file %s" % e)
            return

        for xform_doc in iter_docs(XFormInstance.get_db(), form_ids):
            try:
                xform = XFormInstance.wrap(xform_doc)
                xform.archive(user_id=archiving_user)
                print("Archived form %s in domain %s" % (
                    xform._id, xform.domain
                ))
            except Exception as e:
                print("Issue archiving XFORM %s for domain %s: %s" % (
                    xform_doc['_id'], xform_doc['domain'], e
                ))
