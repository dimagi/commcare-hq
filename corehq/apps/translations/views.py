from django.views.decorators.http import require_GET

from corehq.apps.translations.models import Translation
from dimagi.utils.web import json_response, json_request


@require_GET
def get_translations(request):
    params = json_request(request.GET)
    lang = params.get('lang', 'en')
    key = params.get('key', None)
    one = params.get('one', False)
    return json_response(Translation.get_translations(lang, key, one))
