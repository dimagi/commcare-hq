import json
import re
from couchdbkit import ResourceNotFound
from django.core.cache import cache
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.domain.decorators import determine_authtype_from_user_agent
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


def get_version_from_build_id(domain, build_id):
    """
    fast lookup of app version number given build_id

    implemented as simple caching around _get_version_from_build_id

    """
    if not build_id:
        return None
    cache_key = 'build_id_to_version/{}/{}'.format(domain, build_id)
    cache_value = cache.get(cache_key)
    if not cache_value:
        # serialize as json to distinguish cache miss (None)
        # from a None value ('null')
        cache_value = json.dumps(_get_version_from_build_id(domain, build_id))
        cache.set(cache_key, cache_value, 24*60*60)
    return json.loads(cache_value)


def _get_version_from_build_id(domain, build_id):
    try:
        build = ApplicationBase.get(build_id)
    except ResourceNotFound:
        return None
    if not build.copy_of:
        return None
    elif build.domain != domain:
        return None
    else:
        return build.version


def get_version_from_appversion_text(appversion_text):
    """
    >>> # these first two could certainly be replaced
    >>> # with more realistic examples, but I didn't have any on hand
    >>> get_version_from_appversion_text('foofoo #102 barbar')
    102
    >>> get_version_from_appversion_text('foofoo b[99] barbar')
    99
    >>> get_version_from_appversion_text(
    ...     'CommCare ODK, version "2.11.0"(29272). App v65. '
    ...     'CommCare Version 2.11. Build 29272, built on: February-14-2014'
    ... )
    65
    >>> get_version_from_appversion_text(
    ...     'CommCare ODK, version "2.4.1"(10083). App v19.'
    ...     'CommCare Version 2.4. Build 10083, built on: March-12-2013'
    ... )
    19

    """

    patterns = [
        r' #(\d+) ',
        'b\[(\d+)\]',
        r'App v(\d+).',
    ]
    if appversion_text:
        for pattern in patterns:
            match = re.search(pattern, appversion_text)
            if match:
                build_number, = match.groups()
                return int(build_number)


class BuildVersionSource:
    BUILD_ID = object()
    APPVERSION_TEXT = object()
    XFORM_VERSION = object()
    NONE = object()


def get_build_version(xform):
    """
    there are a bunch of unreliable places to look for a build version
    this abstracts that out

    """

    version = get_version_from_build_id(xform.domain, xform.build_id)
    if version:
        return version, BuildVersionSource.BUILD_ID

    version = get_version_from_appversion_text(
        get_meta_appversion_text(xform)
    )
    if version:
        return version, BuildVersionSource.APPVERSION_TEXT

    xform_version = xform.version
    if xform_version and xform_version != '1':
        return int(xform_version), BuildVersionSource.XFORM_VERSION

    return None, BuildVersionSource.NONE


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


def determine_authtype(request):
    if request.GET.get('authtype'):
        return request.GET['authtype']

    return determine_authtype_from_user_agent(request)
