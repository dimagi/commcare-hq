from couchdbkit.client import Database
from django.conf import settings


def get_docs(schema_index):
    db = Database(settings.COUCH_DATABASE)
    return [result['doc'] for result in db.view("couchexport/schema_index", key=schema_index, include_docs=True).all()]

def get_schema(docs):
    return make_schema(docs)

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
    if doc_kind == "null":
        return schema

    if schema_kind != "list" and doc_kind == "list":
        schema_kind = "list"
        schema = [schema]
    
    if schema_kind == "null":
        return make_schema(doc)
    elif schema_kind == "dict":
        if doc_kind == "dict":
            for key in doc:
                schema[key] = extend_schema(schema.get(key, None), doc[key])
            return schema
    elif schema_kind == "list":
        if doc_kind == "list":
            for doc_ in doc:
                schema[0] = extend_schema(schema[0], doc_)
            return schema
    elif schema_kind == "string":
        if doc_kind == "string":
            return "string"

    raise SchemaInferenceError("Mismatched schema (%r) and doc (%r)" % (schema, doc))