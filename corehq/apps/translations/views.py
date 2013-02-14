import json
from django.http import Http404, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render

from corehq.apps.translations.models import Translation, TranslationMixin
from dimagi.utils.web import json_response, json_request

def validate_trans_doc(trans, request, domain=None):
    if trans.doc_type == "TranslationDoc":
        raise Http404
    elif trans.doc_type == "Application":
        if trans['domain'] != domain:
            raise Http404
        elif not request.couch_user.can_edit_apps(domain):
            return HttpResponseForbidden()
    else:
        raise Http404

@require_GET
def get_translations(request):
    params = json_request(request.GET)
    lang = params.get('lang', 'en')
    key  = params.get('key', None)
    one  = params.get('one', False)
    return json_response(Translation.get_translations(lang, key, one))

@require_POST
def set_translations(request):
    params          = json_request(request.POST)
    doc_id          = params.get('doc_id')
    lang            = params.get('lang')
    translations    = params.get('translations')

    trans = TranslationMixin.get(doc_id)

    trans.set_translations(lang, translations)
    resp = {}
    try:
        trans.save(response_json=resp)
    except Exception:
        trans.save()
    return json_response(resp)

@require_GET
def edit(request, template="translations/edit.html"):
    params = json_request(request.GET)
    doc_id  = params.get('doc_id')
    lang    = params.get('lang')

    trans = TranslationMixin.get(doc_id)
    validate_trans_doc(trans)
    return render(request, template, {
        "translations_json": json.dumps(trans.translations[lang]),
        "doc_id": doc_id,
        "lang": lang
    })
