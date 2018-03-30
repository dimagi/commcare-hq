from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.urls import reverse
from six.moves.urllib.parse import quote


def should_show_preview_app(request, app, username):
    return not app.is_remote_app()


def webapps_url(domain, app_id=None, module_id=None, form_id=None, case_id=None):
    url = reverse('formplayer_main', args=[domain])
    query_dict = {}
    if app_id:
        query_dict['appId'] = app_id
        if module_id is not None:
            query_dict['steps'] = [module_id]
            query_dict['page'] = None
            query_dict['search'] = None
            if form_id is not None:
                query_dict['steps'].append(form_id)
                if case_id is not None:
                    query_dict['steps'].append(case_id)
    query_string = quote(json.dumps(query_dict))
    return "{base_url}#{query}".format(base_url=url, query=query_string)
