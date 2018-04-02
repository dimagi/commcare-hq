from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import os

from django.core.management.base import BaseCommand

from couchdbkit.exceptions import ResourceNotFound
from dimagi.utils.couch.database import get_db


# possible expansion: allow this to accept doc ids on the command line
# for use like `cat doc_ids.txt | ./manage.py get_doc_domains `xargs echo`
class Command(BaseCommand):
    help = "Takes a file with one doc id per line and outputs their domains"

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            dest='full',
            default=False,
            help="Output a full list of doc ids, followed by their domain",
        )

    def handle(self, filename, **options):
        self.full = options.get('full')
        if not os.path.exists(filename):
            return "File %s not found" % filename
        with open(filename) as file:
            doc_ids = file.readlines()
        self.domains = set()
        self.db = get_db()
        for id in doc_ids:
            self.handle_doc(id.strip())

    def handle_doc(self, id):
        try:
            doc = self.db.get(id)
        except ResourceNotFound:
            doc = {}
        domain = doc.get('domain', None)
        if self.full:
            doc_type = doc.get('doc_type', None)
            print("{0},{1},{2}".format(id, domain, doc_type))
        elif domain and domain not in self.domains:
            self.domains.add(domain)
            print(domain)
