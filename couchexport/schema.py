from couchdbkit.client import Database
from django.conf import settings
from couchdbkit.consumer import Consumer
from couchexport.models import ExportSchema


def get_docs(schema_index, previous_export=None, filter=None):
    
    def _filter(results):
        if filter is None:
            return results
        return [doc for doc in results if filter(doc)]
            
    db = Database(settings.COUCH_DATABASE)
    if previous_export is not None:
        consumer = Consumer(db)
        view_results = consumer.fetch(since=previous_export.seq)
        include_ids = set([res["id"] for res in view_results["results"]])
        possible_ids = set([result['id'] for result in \
                            db.view("couchexport/schema_index", 
                                    key=schema_index).all()])
        ids_to_use = include_ids.intersection(possible_ids)
        return _filter(res["doc"] for res in \
                       db.all_docs(keys=list(ids_to_use), include_docs=True).all())
    else: 
        return _filter([result['doc'] for result in \
                        db.view("couchexport/schema_index", 
                                key=schema_index, include_docs=True).all()])

def build_latest_schema(schema_index):
    """
    Build a schema, directly from the index.
    """
    db = Database(settings.COUCH_DATABASE)
    current_seq = db.info()["update_seq"]
    previous_export = ExportSchema.last(schema_index)
    docs = get_docs(schema_index, previous_export)
    [schema] = get_schema(docs, previous_export)
    if not schema:
        return None
    updated_checkpoint = ExportSchema(seq=current_seq, schema=schema, 
                                      index=schema_index)
    updated_checkpoint.save()
    return updated_checkpoint

def get_schema(docs, previous_export=None):
    if previous_export is None:
        return make_schema(docs)
    else:
        schema = previous_export.schema
        for doc in docs:
            extend_schema(schema, doc)
        return [schema]


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
    if doc_kind != "list" and schema_kind == "list":
        doc_kind = "list"
        doc = [doc]
        
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