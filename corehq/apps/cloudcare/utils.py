import json

from django.urls import reverse

from six.moves.urllib.parse import quote


def should_show_preview_app(request, app, username):
    return not app.is_remote_app()


def _webapps_url(domain, app_id, steps):
    url = reverse('formplayer_main', args=[domain])
    query_dict = {
        'appId': app_id,
        'steps': steps,
        'page': None,
        'search': None,
    }
    query_string = quote(json.dumps(query_dict))
    return "{base_url}#{query}".format(base_url=url, query=query_string)


def webapps_module_form_case(domain, app_id, module_id, form_id, case_id):
    return _webapps_url(domain, app_id, steps=[module_id, form_id, case_id])


def webapps_module_case_form(domain, app_id, module_id, case_id, form_id):
    return _webapps_url(domain, app_id, steps=[module_id, case_id, form_id])


def webapps_module(domain, app_id, module_id):
    return _webapps_url(domain, app_id, steps=[module_id])
