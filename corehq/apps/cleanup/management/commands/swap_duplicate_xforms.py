from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import re
from collections import defaultdict

from datetime import datetime
from uuid import UUID

from django.core.management import BaseCommand

from couchforms.models import XFormInstance, XFormDuplicate
from six.moves import input
from io import open


PROBLEM_TEMPLATE_START = "This document was an xform duplicate that replaced "
# This string will be used in the problem field of fixed xforms.
FIXED_FORM_PROBLEM_TEMPLATE = PROBLEM_TEMPLATE_START + "{id_} on {datetime_}"
BAD_FORM_PROBLEM_TEMPLATE = "Form was missing multimedia attachments. Replaced by {} on {}"


class Command(BaseCommand):
    help = 'Replace xforms missing attachments with xfrom duplicates containing attachments.'

    def add_arguments(self, parser):
        parser.add_argument('ids_file_path')
        parser.add_argument('log_path')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help="Don't do the actual modifications, but still log what would be affected."
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            dest='no_input',
            default=False,
            help='Skip important confirmation warnings.'
        )

    def handle(self, ids_file_path, log_path, **options):

        self.dups_by_domain = {}
        # e.g.
        #   {
        #       "foo-domain": {
        #           "an-original-id": {"a-duplicate-id", "another-duplicate-id"}
        #       }
        #   }

        dry_run = options.get("dry_run", True)
        if not options.get('no_input', False) and not dry_run:
            confirm = input(
                """
                Are you sure you want to swap the given XFormInstances for duplicates?
                This is NOT a dry run. y/N?
                """
            )
            if confirm != "y":
                print("\n\t\tSwap duplicates cancelled.")
                return

        ids_file_path = ids_file_path.strip()
        log_path = log_path.strip()

        one_dup_counts = defaultdict(lambda: 0)
        multi_dups_counts = defaultdict(lambda: 0)
        no_dups_counts = defaultdict(lambda: 0)

        with open(log_path, "w") as log_file:
            with open(ids_file_path, "r") as lines:

                total_lines = 0
                for _ in lines:
                    total_lines += 1
                lines.seek(0)

                for i, (domain, bad_xform_id) in enumerate(l.split() for l in lines):
                    self._print_progress(i, total_lines)
                    duplicates = self.get_duplicates(domain, bad_xform_id)
                    if len(duplicates) == 1:
                        one_dup_counts[domain] += 1
                        self.swap_doc_types(
                            log_file, bad_xform_id, list(duplicates)[0], domain, dry_run
                        )
                    elif len(duplicates) > 1:
                        multi_dups_counts[domain] += 1
                        self.log_too_many_dups(log_file, bad_xform_id, domain, duplicates)
                    else:
                        self.log_no_dups(log_file, bad_xform_id, domain)
                        no_dups_counts[domain] += 1

        print("Found {} forms with no duplicates".format(sum(no_dups_counts.values())))
        print("Found {} forms with one duplicate".format(sum(one_dup_counts.values())))
        print("Found {} forms with multiple duplicates".format(sum(multi_dups_counts.values())))
        print("")
        domains = set(no_dups_counts.keys()) | set(one_dup_counts.keys()) | set(multi_dups_counts.keys())
        domains = sorted(list(domains))
        for domain in domains:
            print(domain)
            print("\t{} forms with no duplicates".format(no_dups_counts[domain]))
            print("\t{} forms with one duplicate". format(one_dup_counts[domain]))
            print("\t{} forms with multiple duplicates".format(multi_dups_counts[domain]))

    def get_duplicates(self, domain, xform_id):

        if domain not in self.dups_by_domain:
            self.populate_dup_map(domain)
        return self.dups_by_domain[domain].get(UUID(xform_id), {})

    def populate_dup_map(self, domain):
        self.dups_by_domain[domain] = defaultdict(set)
        dups = XFormInstance.view(
            'couchforms/all_submissions_by_domain',
            startkey=[domain, 'XFormDuplicate', '2016'],
            endkey=[domain, "XFormDuplicate", {}],
            reduce=False,
            include_docs=True
        )
        for dup in dups:
            match = re.match(r'Form is a duplicate of another! \((.*)\)', dup.problem or "")
            if match:
                orig_id = match.groups()[0]
                try:
                    orig_id = UUID(orig_id)
                except ValueError:
                    continue
                self.dups_by_domain[domain][orig_id].add(dup._id)

    def swap_doc_types(self, log_file, bad_xform_id, duplicate_xform_id, domain, dry_run):
        bad_xform = XFormInstance.get(bad_xform_id)

        # confirm that the doc hasn't already been fixed:
        bad_xform_problem = None
        try:
            bad_xform_problem = bad_xform.problem or ""
        except AttributeError:
            pass
        if bad_xform_problem:
            if re.match(PROBLEM_TEMPLATE_START, bad_xform_problem):
                self.log_already_fixed(log_file, bad_xform_id, domain)
                return

        duplicate_xform = XFormInstance.get(duplicate_xform_id)
        now = datetime.now().isoformat()

        # Convert the XFormInstance to an XFormDuplicate
        bad_xform.doc_type = XFormDuplicate.__name__
        bad_xform.problem = BAD_FORM_PROBLEM_TEMPLATE.format(duplicate_xform_id, now)
        bad_xform = XFormDuplicate.wrap(bad_xform.to_json())

        # Convert the XFormDuplicate to an XFormInstance
        duplicate_xform.problem = FIXED_FORM_PROBLEM_TEMPLATE.format(
            id_=bad_xform_id, datetime_=now
        )
        duplicate_xform.doc_type = XFormInstance.__name__
        duplicate_xform = XFormInstance.wrap(duplicate_xform.to_json())

        self.log_swap(log_file, bad_xform_id, domain, duplicate_xform_id, dry_run)

        if not dry_run:
            duplicate_xform.save()
            bad_xform.save()

    @staticmethod
    def log_too_many_dups(log_file, bad_xform_id, domain, duplicates):
        log_file.write(
            "Multiple duplicates for {} in {}. Duplicates: {}\n".format(
                bad_xform_id,
                domain,
                ", ".join(d for d in duplicates)
            )
        )

    @staticmethod
    def log_swap(log_file, bad_xform_id, domain, duplicate_xform_id, dry_run):
        if dry_run:
            prefix = "Would have swapped"
        else:
            prefix = "Swapped"
        log_file.write(
            "{} bad xform {} for duplicate {} in {}\n".format(
                prefix, bad_xform_id, duplicate_xform_id, domain
            )
        )

    @staticmethod
    def log_no_dups(log_file, bad_xform_id, domain):
        log_file.write("No duplicates found for {} in {}\n".format(bad_xform_id, domain))

    @staticmethod
    def log_already_fixed(log_file, bad_xform_id, domain):
        log_file.write("Already fixed xform {} in {}".format(bad_xform_id, domain))

    @staticmethod
    def _print_progress(i, total_submissions):
        if i % 20 == 0 and i != 0:
            print("Progress: {} of {} ({})  {}".format(
                i, total_submissions, round(i / float(total_submissions), 2), datetime.now()
            ))
