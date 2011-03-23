from couchdbkit.client import Database
from django.conf import settings


def get_docs(schema_index):
    db = Database(settings.COUCH_DATABASE)
    return [result['doc'] for result in db.view("couchexport/schema_index", key=schema_index, include_docs=True).all()]

def get_schema(docs):
    return make_schema(docs)

def make_schema(doc):
    if isinstance(doc, list):
        schema = None
        for doc in docs:
            schema = extend_schema(schema, doc)
        return schema

class SchemaInferenceError(Exception):
    pass

def extend_schema(schema, doc):
    schema_inference_error = SchemaInferenceError("Mismatched schema (%r) and doc (%r)" % (schema, doc))
    schema_kind = get_kind()
    if schema is None:
        return make_schema(doc)
    elif isinstance(schema, dict):
        if isinstance(doc, dict):
            for key in doc:
                schema[key] = extend_schema(schema.get(key, None), doc[key])
        else:
            raise schema_inference_error
    elif isinstance(schema, list):
        if isinstance(doc, list):
            for doc_ in doc:
                schema[0] = extend_schema(schema[0], doc_)
        else:
            raise schema_inference_error
    else:
        