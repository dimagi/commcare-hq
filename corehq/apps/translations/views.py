# Create your views here.
import json
from django.views.decorators.http import require_GET, require_POST
from corehq.apps.translations.models import Translation, TranslationMixin
from dimagi.utils.web import json_response, json_request, render_to_response

@require_GET
def get_translations(request):
    params = json_request(request.GET)
    lang = params.get('lang', 'en')
    key  = params.get('key', None)
    one  = params.get('one', False)
    return json_response(Translation.get_translations(lang, key, one))

@require_POST
def set_translation(request):
    params = json_request(request.POST)
    doc_id  = params.get('doc_id')
    lang    = params.get('lang')
    key     = params.get('key')
    value   = params.get('value')
    trans = TranslationMixin.get(doc_id)
    assert(trans.doc_type in ("TranslationDoc",))
    trans.set_translation(lang, key, value)
    trans.save()
    return json_response({"key": key, "value": value})

@require_GET
def edit(request, template="translations/edit.html"):
    params = json_request(request.GET)
    doc_id  = params.get('doc_id')
    lang    = params.get('lang')

    trans = TranslationMixin.get(doc_id)
    assert(trans.doc_type in ("TranslationDoc",))
    return render_to_response(request, template, {
        "translations_json": json.dumps(trans.translations[lang]),
        "doc_id": doc_id,
        "lang": lang
    })