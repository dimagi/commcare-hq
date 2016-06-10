from optparse import make_option

from datetime import datetime
from django.core.management import BaseCommand

from corehq.apps.es import FormES
from corehq.apps.es.filters import term
from couchforms.models import XFormInstance, XFormDuplicate, XFormError


class Command(BaseCommand):
    help = 'Replace xforms missing attachments with xfrom duplicates containing attachments.'
    args = '<ids_file_path> <log_path>'

    option_list = BaseCommand.option_list + (
        make_option(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help="Don't do the actual modifications, but still log what would be affected."
        ),
    )

    def handle(self, *args, **options):

        dry_run = options.get("dry_run", True)
        ids_file_path = args[0].strip()
        log_path = args[1].strip()

        with open(log_path, "w") as log_file:
            with open(ids_file_path, "r") as ids:
                for bad_xform_id in ids:
                    duplicates = self.get_duplicates(bad_xform_id)
                    if len(duplicates) == 1:
                        self.swap_doc_types(log_file, bad_xform_id, duplicates[0]['_id'], dry_run)
                    elif len(duplicates) > 1:
                        self.log_too_many_dups(log_file, bad_xform_id, duplicates)

    @staticmethod
    def get_duplicates(xform_id):
        query = (FormES()
                 .remove_default_filters()
                 .doc_type("XFormDuplicate")  # TODO: Possible this needs to be xformduplicate
                 .filter(term('orig_id', xform_id)))
        return query.run().hits

    @staticmethod
    def swap_doc_types(log_file, bad_xform_id, duplicate_xform_id, dry_run):
        bad_xform = XFormInstance.get(bad_xform_id)
        duplicate_xform = XFormDuplicate.get(duplicate_xform_id)

        # Convert the XFormInstance to an XFormDuplicate
        bad_xform.doc_type = XFormDuplicate.__name__
        bad_xform.orig_id = duplicate_xform._id

        # Convert the XFormDuplicate to an XFormInstance
        del duplicate_xform.orig_id  # TODO: Does CouchDBKit allow del?
        duplicate_xform.doc_type = XFormInstance.__name__

        # TODO: Log the change
        if not dry_run:
            duplicate_xform.save()
            bad_xform.save()

    @staticmethod
    def log_too_many_dups(log_file, bad_xform_id, duplicates):
        log_file.write(
            "Multiple duplicates for {}. Duplicates: {}".format(
                bad_xform_id,
                ", ".join(d['_id'] for d in duplicates)
            )
        )

    # @staticmethod
    # def _print_progress(i, total_submissions):
    #     if i % 200 == 0 and i != 0:
    #         print "Progress: {} of {} ({})  {}".format(
    #             i, total_submissions, round(i / float(total_submissions), 2), datetime.now()
    #         )
