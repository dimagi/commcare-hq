from collections import defaultdict

import logging

from django.core.management.base import BaseCommand

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.modules import to_function

from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
        Given a couch document type, iterates over all documents and reports back
        on usage of each attribute, to aid in selecting SQL fields for those attributes.

        For each attribute report:
        - Whether the value is ever None, for the purpose of deciding whether to use null=True
        - Longest value, for the purpose of setting max_length

        Boolean attributes are ignored. Any attributes that is a list of dicts is assumed to be SchemaListProperty,
        and each of its attributes is examined the same way as a top-level attribute.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'django_app',
        )
        parser.add_argument(
            'class_name',
        )

    def handle(self, django_app, class_name, **options):
        path = f"corehq.apps.{django_app}.models.{class_name}"
        couch_class = to_function(path)
        while not couch_class:
            path = input(f"Could not find {path}, please enter path: ")
            couch_class = to_function(path)
            class_name = path.split(".")[-1]

        key_counts = defaultdict(lambda: 0)
        max_lengths = defaultdict(lambda: 0)
        doc_ids = get_doc_ids_by_class(couch_class)

        print("Found {} {} docs\n".format(len(doc_ids), class_name))

        def _evaluate_doc(doc, prefix=None):
            for key, value in doc.items():
                if prefix:
                    key = f"{prefix}.{key}"
                if value is None:
                    continue

                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            _evaluate_doc(item, prefix=key)
                elif isinstance(value, dict):
                    _evaluate_doc(value, prefix=key)
                else:
                    length = len(str(value))
                    max_lengths[key] = max(length, max_lengths[key])
                key_counts[key] += 1

        for doc in iter_docs(couch_class.get_db(), doc_ids):
            _evaluate_doc(doc)

        max_count = max(key_counts.values())
        for key in sorted(key_counts):
            print("{} is {} null and has max length of {}".format(
                key,
                'never' if key_counts[key] == max_count else 'sometimes',
                max_lengths[key]
            ))
