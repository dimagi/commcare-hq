from collections import defaultdict

import logging

from django.core.management.base import BaseCommand

from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types, get_doc_count_by_type
from corehq.util.couchdb_management import couch_config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
        Given a set of attributes and a couch document type, Iterates over all documents
        and reports back on whether those attributes are ever null and what their largest
        values are.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'doc_type',
        )
        parser.add_argument(
            '-a',
            '--attrs',
            nargs='+',
        )
        parser.add_argument(
            '-s',
            '--db',
            dest='db',
            help='Slug for couch data base. Leave off if querying main commcarehq db.',
        )

    def handle(self, doc_type, **options):
        attrs = options.get('attrs', [])
        db = couch_config.get_db(options.get('db', None))
        blank_counts = defaultdict(lambda: 0)
        max_lengths = defaultdict(lambda: 0)

        print("Found {} {} docs\n".format(get_doc_count_by_type(db, doc_type), doc_type))

        docs = get_all_docs_with_doc_types(db, [doc_type])
        for doc in docs:
            for attr in attrs:
                if doc.get(attr):
                    max_lengths[attr] = max(len(doc[attr]), max_lengths[attr])
                else:
                    blank_counts[attr] += 1

        for attr in attrs:
            print("{} is {} blank and has max length of {}".format(
                attr,
                'sometimes' if blank_counts[attr] else 'never',
                max_lengths[attr]
            ))
