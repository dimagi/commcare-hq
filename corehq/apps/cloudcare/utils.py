import json

from django.urls import reverse

from six.moves.urllib.parse import quote

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.cloudcare.const import MAX_MOBILE_UCR_LIMIT


def should_show_preview_app(request, app, username):
    return not app.is_remote_app()


def _webapps_url(domain, app_id, selections):
    url = reverse('formplayer_main', args=[domain])
    query_dict = {
        'appId': app_id,
        'selections': selections,
        'page': None,
        'search': None,
    }
    query_string = quote(json.dumps(query_dict))
    return "{base_url}#{query}".format(base_url=url, query=query_string)


def webapps_module_form_case(domain, app_id, module_id, form_id, case_id):
    return _webapps_url(domain, app_id, selections=[module_id, form_id, case_id])


def webapps_module_case_form(domain, app_id, module_id, case_id, form_id):
    return _webapps_url(domain, app_id, selections=[module_id, case_id, form_id])


def webapps_module(domain, app_id, module_id):
    return _webapps_url(domain, app_id, selections=[module_id])


def exceeds_mobile_ucr_limit(domain):
    """
    The limit is only applicable if MOBILE_UCR is enabled
    Checks the number of UCRs referenced across all applications in a domain
    :returns: True if the total number exceeds the limit set in const.MAX_MOBILE_UCR_LIMIT
    """
    if not toggles.MOBILE_UCR.enabled(domain):
        return False

    apps = get_apps_in_domain(domain, include_remote=False)
    ucrs = [
        ucr
        for app in apps
        for module in app.get_report_modules()
        for ucr in module.report_configs
    ]
    return len(ucrs) > MAX_MOBILE_UCR_LIMIT
