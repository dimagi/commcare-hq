import re
from couchdbkit import ResourceNotFound
from django.core.cache import cache
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from couchforms.models import DefaultAuthContext
import couchforms


def get_submit_url(domain, app_id=None):
    if app_id:
        return "/a/{domain}/receiver/{app_id}/".format(domain=domain, app_id=app_id)
    else:
        return "/a/{domain}/receiver/".format(domain=domain)


def submit_form_locally(instance, domain, **kwargs):
    # intentionally leave these unauth'd for now
    kwargs['auth_context'] = kwargs.get('auth_context') or DefaultAuthContext()
    response = couchforms.SubmissionPost(
        domain=domain,
        instance=instance,
        **kwargs
    ).get_response()
    if not 200 <= response.status_code < 300:
        raise LocalSubmissionError('Error submitting (status code %s): %s' % (
            response.status_code,
            response.content,
        ))
    return response


def get_meta_appversion_text(xform):
    form_data = xform.form
    try:
        text = form_data['meta']['appVersion']['#text']
    except KeyError:
        return None

    # just make sure this is a longish string and not something like '2.0'
    if isinstance(text, (str, unicode)) and len(text) > 5:
        return text
    else:
        return None


def get_build_version(xform):
    """
    there are a bunch of unreliable places to look for a build version
    this abstracts that out

    """
    patterns = [
        r' #(\d+) ',
        'b\[(\d+)\]',
    ]

    appversion_text = get_meta_appversion_text(xform)
    if appversion_text:
        for pattern in patterns:
            match = re.search(pattern, appversion_text)
            if match:
                build_number, = match.groups()
                return int(build_number)

    xform_version = xform.version
    if xform_version and xform_version != '1':
        return int(xform_version)


def get_app_and_build_ids(domain, build_or_app_id):
    if build_or_app_id:
        cache_key = 'build_to_app_id' + build_or_app_id
        cache_value = cache.get(cache_key)
        if cache_value is None:
            cache_value = _get_app_and_build_ids(domain, build_or_app_id)
            cache.set(cache_key, cache_value, 24*60*60)
        return cache_value
    else:
        app_id, build_id = build_or_app_id, None
    return app_id, build_id


def _get_app_and_build_ids(domain, build_or_app_id):
    try:
        app_json = ApplicationBase.get_db().get(build_or_app_id)
    except ResourceNotFound:
        pass
    else:
        if domain == app_json.get('domain'):
            copy_of = app_json.get('copy_of')
            if copy_of:
                return copy_of, build_or_app_id
    return build_or_app_id, None
