from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import os
import sys

from collections import defaultdict
from io import open

import csv342 as csv
from django.core.management.base import BaseCommand
from six.moves import input

from corehq.util.log import with_progress_bar

from ...models import PhoneNumber, SQLMobileBackend
from ...util import clean_phone_number


class Command(BaseCommand):
    help = "Reassign phone numbers with old backend id to new backend id"

    def add_arguments(self, parser):
        parser.add_argument("old_backend", help="Old backend ID")
        parser.add_argument("--new-backend", help=(
            "New backend ID. Dry-run if this option is absent. Use 'None' "
            "to clear the old backend without specifying a new backend; "
            "the phone number will use the domain/system default backend."
        ))
        parser.add_argument("--domain", help="Limit to phone numbers in domain.")
        parser.add_argument("--dump-csv",
            help="Dump phone numbers to CSV file path "
                 "(the path is the value given for this option).")

    def handle(self, old_backend, new_backend=None, domain=None, **options):
        query = PhoneNumber.objects.filter(backend_id=old_backend)
        if domain is not None:
            query = query.filter(domain=domain)

        if options["dump_csv"]:
            dump_csv(query, options["dump_csv"])

        print_counts_by_default_backend(query)
        print("Total assigned to {}: {}".format(old_backend, len(query)))

        if new_backend:
            reassign(query, new_backend)


def dump_csv(query, path):
    path = os.path.expanduser(path)
    print("dumping to CSV: {}".format(path))
    with open(path, "w", encoding="utf-8") as output:
        csvfile = csv.writer(output)
        csvfile.writerow(["domain", "couch_id", "phonenumber"])
        for phone in query:
            csvfile.writerow([
                phone.domain,
                phone.couch_id,
                phone.phone_number,
            ])


def print_counts_by_default_backend(query):
    counts = defaultdict(int)
    for phone in with_progress_bar(query, len(query), oneline=True):
        default_backend = SQLMobileBackend.load_default_by_phone_and_domain(
            SQLMobileBackend.SMS,
            clean_phone_number(phone.phone_number),
            domain=phone.domain
        )
        counts[default_backend.name] += 1
    print("Counts by default backend")
    for default, count in sorted(counts.items()):
        print("{:<25}{:>4}".format(default, count))


def reassign(query, new_backend):
    if new_backend == "None":
        new_backend = None
    ok = confirm("Reassign to {}".format(new_backend))
    if ok:
        updated = query.update(backend_id=new_backend)
        print("{} phone numbers updated".format(updated))
    else:
        print("abort")
        sys.exit(1)


def confirm(msg):
    return input(msg + " (y/N) ").lower() == 'y'
