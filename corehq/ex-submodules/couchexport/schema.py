from couchdbkit.client import Database
from django.conf import settings
from couchexport.exceptions import SchemaInferenceError
from couchexport.models import ExportSchema


def build_latest_schema(schema_index):
    """
    Build a schema, directly from the index. Also creates a saved checkpoint.
    """
    from couchexport.export import ExportConfiguration
    db = Database(settings.COUCH_DATABASE)
    previous_export = ExportSchema.last(schema_index)
    config = ExportConfiguration(db, schema_index,
                                 previous_export=previous_export)
    schema = config.get_latest_schema()
    if not schema:
        return None
    updated_checkpoint = config.create_new_checkpoint()
    return updated_checkpoint


def get_kind(doc):
    if doc == "" or doc is None:
        return "null"
    elif isinstance(doc, dict):
        return "dict"
    elif isinstance(doc, list):
        return "list"
    else:
        return "string"


def make_schema(doc):
    doc_kind = get_kind(doc)
    if doc_kind == "null":
        return None
    elif doc_kind == "dict":
        schema = {}
        for key in doc:
            schema[key] = make_schema(doc[key])
        return schema
    elif doc_kind == "list":
        schema = None
        for doc_ in doc:
            schema = extend_schema(schema, doc_)
        return [schema]
    elif doc_kind == "string":
        return "string"


def extend_schema(previous_schema, schema):
    """
    Reconciles the previous_schema with the new schema
    """
    previous_schema_kind = get_kind(previous_schema)
    schema_kind = get_kind(schema)

    # 1. anything + null => anything
    if schema_kind == "null":
        return previous_schema
    if previous_schema_kind == "null":
        return make_schema(schema)

    # 2. not-list => [not-list] when compared to a list
    if previous_schema_kind != "list" and schema_kind == "list":
        previous_schema_kind = "list"
        previous_schema = [previous_schema]
    if schema_kind != "list" and previous_schema_kind == "list":
        schema_kind = "list"
        schema = [schema]

    # 3. not-dict => {'': not-dict} when compared to a dict
    if previous_schema_kind != 'dict' and schema_kind == 'dict':
        if not previous_schema_kind == 'string':
            raise SchemaInferenceError("%r is type %r but should be type 'string'!!" % (previous_schema,
                previous_schema_kind))
        previous_schema_kind = 'dict'
        previous_schema = {'': previous_schema_kind}
    if schema_kind != 'dict' and previous_schema_kind == 'dict':
        if not schema_kind == 'string':
            raise SchemaInferenceError("%r is type %r but should be type 'string'!!" % (schema, schema_kind))
        schema_kind = 'dict'
        schema = {'': schema_kind}

    # 4. Now that previous_schema and schema are of the same kind
    if previous_schema_kind == schema_kind == "dict":
        for key in schema:
            previous_schema[key] = extend_schema(previous_schema.get(key, None), schema[key])
        return previous_schema
    if previous_schema_kind == schema_kind == "list":
        for schema_ in schema:
            previous_schema[0] = extend_schema(previous_schema[0], schema_)
        return previous_schema
    if previous_schema_kind == schema_kind == "string":
            return "string"

    # 5. We should have covered every case above, but if not, fail hard
    raise SchemaInferenceError("Mismatched previous_schema (%r) and schema (%r)" % (previous_schema, schema))
