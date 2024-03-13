import json

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.es.es_query import ESQuery
from corehq.apps.es.transient_util import iter_index_cnames
from corehq.apps.hqwebapp.doc_lookup import (
    get_databases,
    get_db_from_db_name,
    lookup_id_in_databases,
)
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.form_processor.models import XFormInstance
from corehq.util.download import get_download_response
from corehq.util.json import CommCareJSONEncoder


@require_superuser
def doc_in_es(request):
    doc_id = request.GET.get("id")
    if not doc_id:
        return render(request, "hqadmin/doc_in_es.html", {})

    def to_json(doc):
        return json.dumps(doc, indent=4, sort_keys=True) if doc else "NOT FOUND!"

    found_indices = {}
    es_doc_type = None
    for index in iter_index_cnames():
        es_doc = lookup_doc_in_es(doc_id, index)
        if es_doc:
            found_indices[index] = to_json(es_doc)
            es_doc_type = es_doc_type or es_doc.get('doc_type')

    context = {
        "doc_id": doc_id,
        "es_info": {
            "status": "found" if found_indices else "NOT FOUND IN ELASTICSEARCH!",
            "doc_type": es_doc_type,
            "found_indices": found_indices,
        },
        "couch_info": raw_doc_lookup(doc_id),
    }
    return render(request, "hqadmin/doc_in_es.html", context)


def lookup_doc_in_es(doc_id, index):
    res = ESQuery(index).doc_id([doc_id]).run()
    if res.total == 1:
        return res.hits[0]


@require_superuser
def raw_doc(request):
    doc_id = request.GET.get("id")
    db_name = request.GET.get("db_name", None)
    if db_name and "__" in db_name:
        db_name = db_name.split("__")[-1]
    context = raw_doc_lookup(doc_id, db_name) if doc_id else {}

    if request.GET.get("raw", False):
        if 'doc' in context:
            return HttpResponse(context['doc'], content_type="application/json")
        else:
            return HttpResponse(json.dumps({"status": "missing"}),
                                content_type="application/json", status=404)

    context['all_databases'] = [db for db in get_databases()]
    return render(request, "hqadmin/raw_doc.html", context)


def raw_doc_lookup(doc_id, db_name=None):
    if db_name:
        dbs = [get_db_from_db_name(db_name)]
    else:
        dbs = list(get_databases().values())

    result, db_results = lookup_id_in_databases(doc_id, dbs, find_first=False)
    response = {"db_results": db_results}
    if result:
        serialized_doc = result.get_serialized_doc()
        if isinstance(result.doc, XFormInstance):
            errors, raw_data = check_form_for_errors(result.doc, serialized_doc)
            response["errors"] = errors
            response["raw_data"] = raw_data
        result_dict = result.asdict()
        result_dict["doc"] = json.dumps(
            serialized_doc, indent=4, sort_keys=True, cls=CommCareJSONEncoder
        )
        response.update(result_dict)
    if db_name:
        response['selected_db'] = db_name
    return response


def check_form_for_errors(form, form_doc):
    errors = []
    raw_data = None
    if 'form' not in form_doc:
        errors.append(_('Missing Form XML'))
    elif not form_doc['form']:
        errors.append(_('Form XML not valid. See "Raw Data" section below.'))
        raw_data = form.get_xml()
        if not isinstance(raw_data, str):
            try:
                raw_data = raw_data.decode()
            except (UnicodeDecodeError, AttributeError):
                raw_data = repr(raw_data)

    return errors, raw_data


@require_superuser
def download_blob(request):
    """Pairs with the get_download_url utility and command"""
    key = request.GET.get("key")
    try:
        meta = BlobMeta.objects.partitioned_get(
            domain='__system__',
            type_code=CODES.tempfile,
            partition_value=key,
            key=key,
        )
    except BlobMeta.DoesNotExist:
        raise Http404()
    blob = get_blob_db().get(meta=meta)
    return get_download_response(
        payload=blob,
        content_length=meta.content_length,
        content_type=meta.content_type,
        download=True,
        filename=meta.name,
        request=request,
    )
