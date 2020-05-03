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
        - Expected field type
        - Whether the value is ever None, for the purpose of deciding whether to use null=True
        - Longest value, for the purpose of setting max_length

        For any attribute that is a list or dict, the script will ask whether it's a submodel
        (as opposed to a JsonField) and, if so, examine it the same way as a top-level attribute.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'django_app',
        )
        parser.add_argument(
            'class_name',
        )

    COUCH_FIELDS = {'_id', '_rev', 'doc_type', 'base_doc'}

    FIELD_TYPE_BOOL = 'BooleanField'
    FIELD_TYPE_INTEGER = 'IntegerField'
    FIELD_TYPE_DECIMAL = 'DecimalField'
    FIELD_TYPE_STRING = 'CharField'
    FIELD_TYPE_JSON_LIST = 'JsonField,default=list'
    FIELD_TYPE_JSON_DICT = 'JsonField,default=dict'
    FIELD_TYPE_SUBMODEL_LIST = 'ForeignKey'
    FIELD_TYPE_SUBMODEL_DICT = 'OneToOneField'

    key_counts = defaultdict(lambda: 0)
    max_lengths = defaultdict(lambda: 0)
    field_types = {}

    def evaluate_doc(self, doc, prefix=None):
        for key, value in doc.items():
            if key in self.COUCH_FIELDS:
                continue

            if prefix:
                key = f"{prefix}.{key}"

            if value is None:
                continue

            self.key_counts[key] += 1
            if isinstance(value, list):
                if key not in self.field_types:
                    is_submodel = input(f"Is {key} a submodel (y/n)? ").lower().startswith("y")
                    self.field_types.update({
                        key: self.FIELD_TYPE_SUBMODEL_LIST if is_submodel else self.FIELD_TYPE_JSON_LIST,
                    })
                if self.field_types[key] == self.FIELD_TYPE_SUBMODEL_LIST:
                    for item in value:
                        if isinstance(item, dict):
                            self.evaluate_doc(item, prefix=key)
                    continue

            if isinstance(value, dict):
                if key not in self.field_types:
                    is_submodel = input(f"Is {key} a submodel (y/n)? ").lower().startswith("y")
                    self.field_types.update({
                        key: self.FIELD_TYPE_SUBMODEL_DICT if is_submodel else self.FIELD_TYPE_JSON_DICT,
                    })
                if self.field_types[key] == self.FIELD_TYPE_SUBMODEL_DICT:
                    self.evaluate_doc(value, prefix=key)
                    continue

            # Primitives
            if key not in self.field_types:
                if isinstance(value, bool):
                    self.field_types[key] = self.FIELD_TYPE_BOOL
                elif isinstance(value, str):
                    self.field_types[key] = self.FIELD_TYPE_STRING
                elif int(value) == value:
                    self.field_types[key] = self.FIELD_TYPE_INTEGER
                else:
                    self.field_types[key] = self.FIELD_TYPE_DECIMAL

            if self.field_types[key] == self.FIELD_TYPE_BOOL:
                continue

            if self.field_types[key] == self.FIELD_TYPE_INTEGER:
                if int(value) != value:
                    self.field_types[key] = self.FIELD_TYPE_DECIMAL

            self.max_lengths[key] = max(len(str(value)), self.max_lengths[key])

    def handle(self, django_app, class_name, **options):
        path = f"corehq.apps.{django_app}.models.{class_name}"
        couch_class = to_function(path)
        while not couch_class:
            path = input(f"Could not find {path}, please enter path: ")
            couch_class = to_function(path)
            class_name = path.split(".")[-1]

        doc_ids = get_doc_ids_by_class(couch_class)
        print("Found {} {} docs\n".format(len(doc_ids), class_name))

        for doc in iter_docs(couch_class.get_db(), doc_ids):
            self.evaluate_doc(doc)

        max_count = max(self.key_counts.values())
        for key, field_type in self.field_types.items():
            print("{} is a {}, is {} null and has max length of {}".format(
                key,
                field_type,
                'never' if self.key_counts[key] == max_count else 'sometimes',
                self.max_lengths[key]
            ))
