import logging
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date, parse_datetime

import jinja2
from couchdbkit.ext.django import schema
from requests.exceptions import HTTPError

from dimagi.ext import jsonobject
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

    COUCH_FIELDS = {'_id', '_rev', 'doc_type', 'base_doc', '_attachments'}

    FIELD_TYPE_BOOL = 'models.BooleanField'
    FIELD_TYPE_INTEGER = 'models.IntegerField'
    FIELD_TYPE_DATE = 'models.DateField'
    FIELD_TYPE_DATETIME = 'models.DateTimeField'
    FIELD_TYPE_DECIMAL = 'models.DecimalField'
    FIELD_TYPE_STRING = 'models.CharField'
    FIELD_TYPE_JSON = 'JSONField'
    FIELD_TYPE_SUBMODEL_LIST = 'models.ForeignKey'
    FIELD_TYPE_SUBMODEL_DICT = 'models.OneToOneField'
    FIELD_TYPE_UNKNOWN = 'unknown_type'

    field_types = {}
    field_params = {}
    index_fields = set()

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
        self.correlate_with_couch_schema(self.couch_class)

        models_file = self.models_path[:-(len(self.class_name) + 1)].replace(".", os.path.sep) + ".py"
        sql_model, couch_model_additions = self.generate_models_changes()
        print(f"################# edit {models_file} #################")
        print(sql_model)
        print(f"\n################# update {self.class_name} #################")
        print(couch_model_additions)

        command_file = "populate_" + self.class_name.lower() + ".py"
        command_file = os.path.join("corehq", "apps", self.django_app, "management", "commands", command_file)
        command_content = self.generate_management_command()
        print(f"\n################# add {command_file} #################")
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
                    if parse_date(value):
                        self.init_field(key, self.FIELD_TYPE_DATE)
                    elif parse_datetime(value):
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
                if value is not None and int(value) != value:
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
            self.add_index('domain')
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

    def add_index(self, fields):
        if isinstance(fields, str):
            fields = (fields,)
        elif isinstance(fields, list):
            fields = tuple(fields)
        self.index_fields.add(fields)

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

    def correlate_with_couch_schema(self, couch_class, prefix=None):
        """Iterate through the Couch schema to add missing fields and check field types match
        """
        for name, field in couch_class.properties().items():
            if name in self.COUCH_FIELDS:
                continue

            name = f'{prefix}.{name}' if prefix else name
            schema_type = self.couch_type_to_sql_type(field)
            data_type = self.field_type(name)
            if data_type is None:
                self.init_field(name, schema_type)
                continue

            if data_type == self.FIELD_TYPE_UNKNOWN:
                self.update_field_type(name, self.couch_type_to_sql_type(schema_type))
                continue

            if data_type != schema_type and data_type != self.FIELD_TYPE_JSON:
                print(f"WARNING: type mismatch for {name}. "
                      f"Type from data '{data_type}' != type from schema '{schema_type}'")

            if data_type in (self.FIELD_TYPE_SUBMODEL_DICT, self.FIELD_TYPE_SUBMODEL_LIST):
                if isinstance(field, schema.SchemaProperty):
                    self.correlate_with_couch_schema(field.item_type, prefix=name)
                elif isinstance(field, schema.SchemaDictProperty):
                    self.correlate_with_couch_schema(field._type, prefix=name)

    def couch_type_to_sql_type(self, couch_property):
        type_map = {
            schema.StringProperty: self.FIELD_TYPE_STRING,
            schema.BooleanProperty: self.FIELD_TYPE_BOOL,
            schema.DateTimeProperty: self.FIELD_TYPE_DATETIME,
            jsonobject.DateTimeProperty: self.FIELD_TYPE_DATETIME,
            schema.DateProperty: self.FIELD_TYPE_DATE,
            schema.IntegerProperty: self.FIELD_TYPE_INTEGER,
            schema.DecimalProperty: self.FIELD_TYPE_DECIMAL,
            schema.SchemaProperty: self.FIELD_TYPE_SUBMODEL_DICT,
            schema.DictProperty: self.FIELD_TYPE_SUBMODEL_DICT,
            schema.SchemaDictProperty: self.FIELD_TYPE_SUBMODEL_DICT,
            schema.ListProperty: self.FIELD_TYPE_SUBMODEL_LIST,
            schema.SchemaListProperty: self.FIELD_TYPE_SUBMODEL_LIST,
        }
        exact_match = type_map.get(couch_property.__class__, None)
        if exact_match:
            return exact_match

        for schema_class, type_ in type_map.items():
            if isinstance(couch_property, schema_class):
                return type_

        return self.FIELD_TYPE_UNKNOWN

    def standardize_nulls(self):
        # null defaults to False
        for key, params in self.field_params.items():
            if 'null' in params and not params['null']:
                del self.field_params[key]['null']

    def generate_models_changes(self):
        suggested_fields = []
        migration_field_names = []
        submodels = []
        for key, params in self.field_params.items():
            if self.is_field_type_submodel(key):
                submodels.append(key)
            if self.is_submodel_key(key):
                continue
            arg_list = ", ".join([f"{k}={v}" for k, v, in params.items()])
            suggested_fields.append(f"{key} = {self.field_types[key]}({arg_list})")
            migration_field_names.append(key)
        suggested_fields.append("couch_id = models.CharField(max_length=126, null=True)")
        self.add_index('couch_id')

        index_list = ['models.Index(fields={}),'.format(fields) for fields in self.index_fields]
        db_table = self.django_app.lower() + "_" + self.class_name.replace("_", "").lower()
        sql_model = render_tempate(
            "sql_model.j2",
            import_json=self.FIELD_TYPE_JSON in self.field_types.values(),
            class_name=self.class_name,
            migration_field_names=migration_field_names,
            suggested_fields=suggested_fields,
            index_list=index_list,
            submodels=submodels,
            db_table=db_table
        )

        couch_model_additions = render_tempate(
            "couch_model_additions.j2",
            migration_field_names=migration_field_names,
            class_name=self.class_name
        )

        return sql_model, couch_model_additions

    def generate_management_command(self):
        suggested_updates = []
        submodels = []
        for key, field_type in self.field_types.items():
            if self.is_field_type_submodel(key):
                submodels.append(key)
            if self.is_submodel_key(key):
                continue
            if field_type == self.FIELD_TYPE_DATE:
                suggested_updates.append(f'"{key}": force_to_date(doc.get("{key}")),')
            elif field_type == self.FIELD_TYPE_DATETIME:
                suggested_updates.append(f'"{key}": force_to_datetime(doc.get("{key}")),')
            else:
                suggested_updates.append(f'"{key}": doc.get("{key}"),')

        uri = couch_config.get_db_uri_for_class(self.couch_class)
        db_slug = {uri: slug for slug, uri in couch_config.all_db_uris_by_slug.items()}[uri]

        date_conversions = []
        if self.FIELD_TYPE_DATE in self.field_types.values():
            date_conversions.append("force_to_date")
        if self.FIELD_TYPE_DATETIME in self.field_types.values():
            date_conversions.append("force_to_datetime")

        dates_import = ""
        if date_conversions:
            dates_import = f"from dimagi.utils.dates import {','.join(date_conversions)}"

        return render_tempate(
            "populate_command.j2",
            class_name=self.class_name,
            models_path=self.models_path,
            db_slug=db_slug,
            dates_import=dates_import,
            suggested_updates=suggested_updates,
            submodels=submodels
        )

    def is_submodel_key(self, key):
        return "." in key or self.is_field_type_submodel(key)

    def is_field_type_submodel(self, key):
        return self.field_types[key] in (self.FIELD_TYPE_SUBMODEL_LIST, self.FIELD_TYPE_SUBMODEL_DICT)


def render_tempate(template_filename, **kwargs):
    path = Path(__file__).parent.joinpath("templates")
    templateEnv = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=path))
    template = templateEnv.get_template(template_filename)
    return template.render(**kwargs)
