from couchdbkit.client import Database
from django.conf import settings
from couchexport.models import ExportSchema
from dimagi.utils.couch.database import get_db

def build_latest_schema(schema_index):
    """
    Build a schema, directly from the index. Also creates a saved checkpoint.
    """
    from couchexport.export import ExportConfiguration
    db = Database(settings.COUCH_DATABASE)
    current_seq = db.info()["update_seq"]
    previous_export = ExportSchema.last(schema_index)
    if previous_export and previous_export.seq > current_seq:
        # something weird happened (like the couch database changing)
        # better rebuild from scratch
        previous_export = None
    config = ExportConfiguration(get_db(), schema_index, 
                                 previous_export=previous_export)
    schema = config.get_latest_schema()
    if not schema:
        return None
    updated_checkpoint = config.create_new_checkpoint()
    return updated_checkpoint

class SchemaInferenceError(Exception):
    pass

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


def extend_schema(schema, doc):
    schema_kind = get_kind(schema)
    doc_kind = get_kind(doc)

    # 1. anything + null => anything
    if doc_kind == "null":
        return schema
    if schema_kind == "null":
        return make_schema(doc)

    # 2. not-list => [not-list] when compared to a list
    if schema_kind != "list" and doc_kind == "list":
        schema_kind = "list"
        schema = [schema]
    if doc_kind != "list" and schema_kind == "list":
        doc_kind = "list"
        doc = [doc]

    # 3. not-dict => {'': not-dict} when compared to a dict
    if schema_kind != 'dict' and doc_kind == 'dict':
        if not schema_kind == 'string':
            raise SchemaInferenceError("%r is type %r but should be type 'string'!!" % (schema, schema_kind))
        schema_kind = 'dict'
        schema = {'': schema_kind}
    if doc_kind != 'dict' and schema_kind == 'dict':
        if not doc_kind == 'string':
            raise SchemaInferenceError("%r is type %r but should be type 'string'!!" % (doc, doc_kind))
        doc_kind = 'dict'
        doc = {'': doc_kind}

    # 4. Now that schema and doc are of the same kind
    if schema_kind == doc_kind == "dict":
        for key in doc:
            schema[key] = extend_schema(schema.get(key, None), doc[key])
        return schema
    if schema_kind == doc_kind == "list":
        for doc_ in doc:
            schema[0] = extend_schema(schema[0], doc_)
        return schema
    if schema_kind == doc_kind == "string":
            return "string"

    # 5. We should have covered every case above, but if not, fail hard
    raise SchemaInferenceError("Mismatched schema (%r) and doc (%r)" % (schema, doc))
