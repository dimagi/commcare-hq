import logging
import os

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.modules import to_function

from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.couchdb_management import couch_config

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

    FIELD_TYPE_BOOL = 'models.BooleanField'
    FIELD_TYPE_INTEGER = 'models.IntegerField'
    FIELD_TYPE_DATETIME = 'models.DateTimeField'
    FIELD_TYPE_DECIMAL = 'models.DecimalField'
    FIELD_TYPE_STRING = 'models.CharField'
    FIELD_TYPE_JSON = 'JsonField'
    FIELD_TYPE_SUBMODEL_LIST = 'models.ForeignKey'
    FIELD_TYPE_SUBMODEL_DICT = 'models.OneToOneField'
    FIELD_TYPE_UNKNOWN = ''

    field_types = {}
    field_params = {}

    def handle(self, django_app, class_name, **options):
        self.class_name = class_name
        self.django_app = django_app
        self.models_path = f"corehq.apps.{self.django_app}.models.{self.class_name}"
        self.couch_class = to_function(self.models_path)
        while not self.couch_class:
            self.models_path = input(f"Could not find {self.models_path}, please enter path: ")
            self.couch_class = to_function(self.models_path)
            self.class_name = self.models_path.split(".")[-1]

        doc_ids = get_doc_ids_by_class(self.couch_class)
        print("Found {} {} docs\n".format(len(doc_ids), self.class_name))

        for doc in iter_docs(self.couch_class.get_db(), doc_ids):
            self.evaluate_doc(doc)

        self.standardize_max_lengths()

        models_file = self.models_path[:-(len(self.class_name) + 1)].replace(".", os.path.sep) + ".py"
        models_content = self.generate_models_changes()
        print(f"################# edit {models_file} #################")
        print(models_content)

        command_file = "populate_" + self.class_name.lower() + ".py"
        command_file = os.path.join("corehq", "apps", self.django_app, "management", "commands", command_file)
        command_content = self.generate_management_command()
        print(f"################# add {command_file} #################")
        print(command_content)

    def evaluate_doc(self, doc, prefix=None):
        for key, value in doc.items():
            if key in self.COUCH_FIELDS:
                continue

            if prefix:
                key = f"{prefix}.{key}"

            if isinstance(value, list):
                if not self.field_type(key):
                    if input(f"Is {key} a submodel (y/n)? ").lower().startswith("y"):
                        self.init_field(key, self.FIELD_TYPE_SUBMODEL_LIST)
                    else:
                        self.init_field(key, self.FIELD_TYPE_JSON, {'default': 'list'})
                if self.field_type(key) == self.FIELD_TYPE_SUBMODEL_LIST:
                    for item in value:
                        if isinstance(item, dict):
                            self.evaluate_doc(item, prefix=key)
                continue

            if isinstance(value, dict):
                if not self.field_type(key):
                    if input(f"Is {key} a submodel (y/n)? ").lower().startswith("y"):
                        self.init_field(key, self.FIELD_TYPE_SUBMODEL_DICT)
                    else:
                        self.init_field(key, self.FIELD_TYPE_JSON, {'default': 'dict'})
                if self.field_type(key) == self.FIELD_TYPE_SUBMODEL_DICT:
                    self.evaluate_doc(value, prefix=key)
                continue

            # Primitives
            if not self.field_type(key):
                if isinstance(value, bool):
                    self.init_field(key, self.FIELD_TYPE_BOOL)
                elif isinstance(value, str):
                    if parse_datetime(value):
                        self.init_field(key, self.FIELD_TYPE_DATETIME)
                    else:
                        self.init_field(key, self.FIELD_TYPE_STRING)
                else:
                    try:
                        if int(value) == value:
                            self.init_field(key, self.FIELD_TYPE_INTEGER)
                        else:
                            self.init_field(key, self.FIELD_TYPE_DECIMAL)
                    except TypeError:
                        # Couldn't parse, likely None
                        pass
            if not self.field_type(key):
                self.init_field(key, self.FIELD_TYPE_UNKNOWN)

            if self.field_type(key) == self.FIELD_TYPE_BOOL:
                continue

            if self.field_type(key) == self.FIELD_TYPE_INTEGER:
                if int(value) != value:
                    self.update_field_type(key, self.FIELD_TYPE_DECIMAL)

            self.update_field_max_length(key, len(str(value)))
            self.update_field_null(key, value)

    def init_field(self, key, field_type, params=None):
        self.field_types[key] = field_type
        self.field_params[key] = {
            'max_length': 0,
            'null': False,
        }
        if params:
            self.field_params[key].update(params)
        if field_type == self.FIELD_TYPE_BOOL:
            self.field_params[key]['default'] = "'TODO'"
        if key == 'domain':
            self.field_params[key]['db_index'] = True
        if 'created' in key:
            self.field_params[key]['auto_now_add'] = True
        if 'modified' in key:
            self.field_params[key]['auto_now'] = True

    def field_type(self, key):
        return self.field_types.get(key, None)

    def update_field_type(self, key, value):
        self.field_types[key] = value

    def update_field_max_length(self, key, new_length):
        old_max = self.field_params[key]['max_length']
        self.field_params[key]['max_length'] = max(old_max, new_length)

    def update_field_null(self, key, value):
        self.field_params[key]['null'] = self.field_params[key]['null'] or value is None

    def standardize_max_lengths(self):
        max_lengths = [1, 2, 8, 12, 32, 64, 80, 128, 256, 512, 1000]
        for key, params in self.field_params.items():
            if self.field_types[key] != self.FIELD_TYPE_STRING:
                del self.field_params[key]['max_length']
                continue
            if params['max_length']:
                i = 0
                while i < len(max_lengths) and params['max_length'] > max_lengths[i]:
                    i += 1
                if i < len(max_lengths):
                    params['max_length'] = max_lengths[i]

    def standardize_nulls(self):
        # null defaults to False
        for key, params in self.field_params.items():
            if 'null' in params and not params['null']:
                del self.field_params[key]['null']

    def generate_models_changes(self):
        suggested_fields = []
        migration_field_names = []
        for key, params in self.field_params.items():
            if self.is_submodel_key(key):
                continue
            arg_list = ", ".join([f"{k}={v}" for k, v, in params.items()])
            suggested_fields.append(f"{key} = {self.field_types[key]}({arg_list})")
            migration_field_names.append(key)
        suggested_fields.append(f"couch_id = models.CharField(max_length=126, null=True, db_index=True)")

        field_indent = "\n    "
        field_name_list = "\n            ".join([f'"{f}",' for f in migration_field_names])
        db_table = self.django_app.lower() + "_" + self.class_name.replace("_", "").lower()
        json_import = ""
        if self.FIELD_TYPE_JSON in self.field_types.values():
            json_import = "from django.contrib.postgres.fields import JSONField\n"

        return f"""
{json_import}from django.db import models
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin


class SQL{self.class_name}(SyncSQLToCouchMixin, models.Model):
    {field_indent.join(suggested_fields)}

    class Meta:
        db_table = "{db_table}"

    @classmethod
    def _migration_get_fields(cls):
        return [
            {field_name_list}
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return {self.class_name}


# TODO: Add SyncCouchToSQLMixin and the following methods to {self.class_name}
    @classmethod
    def _migration_get_fields(cls):
        return [
            {field_name_list}
        ]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQL{self.class_name}
        """

    def generate_management_command(self):
        suggested_updates = []
        for key, field_type in self.field_types.items():
            if self.is_submodel_key(key):
                continue
            if field_type == self.FIELD_TYPE_DATETIME:
                suggested_updates.append(f'"{key}": force_to_datetime(doc.get("{key}")),')
            else:
                suggested_updates.append(f'"{key}": doc.get("{key}"),')
        updates_list = "\n                ".join(suggested_updates)

        uri = couch_config.get_db_uri_for_class(self.couch_class)
        db_slug_with_quotes = {uri: slug for slug, uri in couch_config.all_db_uris_by_slug.items()}[uri]
        if db_slug_with_quotes:
            db_slug_with_quotes = f'"{db_slug_with_quotes}"'

        datetime_import = ""
        if self.FIELD_TYPE_DATETIME in self.field_types.values():
            datetime_import = "from dimagi.utils.dates import force_to_datetime\n\n"

        return f"""
{datetime_import}from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return {db_slug_with_quotes}

    @classmethod
    def couch_doc_type(self):
        return '{self.class_name}'

    @classmethod
    def sql_class(self):
        from {self.models_path} import SQL{self.class_name}
        return SQL{self.class_name}

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={{
                {updates_list}
            }})
        return (model, created)
        """

    def is_submodel_key(self, key):
        if self.field_types[key] in (self.FIELD_TYPE_SUBMODEL_LIST, self.FIELD_TYPE_SUBMODEL_DICT):
            return True
        return "." in key
