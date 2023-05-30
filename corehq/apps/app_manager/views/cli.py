from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.text import slugify

from couchdbkit.exceptions import DocTypeError, ResourceNotFound

from dimagi.ext.couchdbkit import Document
from soil import FileDownload

from corehq.apps.api.decorators import api_throttle
from corehq.apps.app_manager.views.utils import get_langs, report_build_time
from corehq.apps.domain.decorators import api_auth
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.tasks import create_files_for_ccz
from corehq.toggles import toggles_enabled_for_request
from corehq.util.view_utils import absolute_reverse, json_error

from ..dbaccessors import (
    get_build_doc_by_version,
    get_current_app,
    get_latest_build_doc,
    get_latest_released_app_doc,
    wrap_app,
)

@json_error
@api_auth()
@api_throttle
def list_apps(request, domain):
    def app_to_json(app):
         return {
            'name': app.name,
            'version': app.version,
            'app_id': app.get_id,
            'download_url': absolute_reverse('direct_ccz', args=[domain],
                                             params={'app_id': app.get_id})
        }
    applications = Domain.get_by_name(domain).applications()
    return JsonResponse({
        'status': 'success',
        'applications': list(map(app_to_json, applications)),
    })


@json_error
def direct_ccz(request, domain):
    """
    You must specify an app_id, and you may specify either 'version' or 'latest'
    latest can be one of:
        release: Latest starred version
        build: Latest version regardless of star
        save: Latest saved version of the application (even without a build)
    If 'version' and 'latest' aren't specified it will default to latest save
    You may also set 'include_multimedia=true' if you need multimedia.
    """

    def error(msg, code=400):
        return JsonResponse({'status': 'error', 'message': msg}, status=code)

    def get_app(app_id, version, latest):
        if version:
            return get_build_doc_by_version(domain, app_id, version)
        elif latest == 'build':
            return get_latest_build_doc(domain, app_id)
        elif latest == 'release':
            return get_latest_released_app_doc(domain, app_id)
        else:
            # either latest=='save' or they didn't specify
            return get_current_app(domain, app_id)

    app_id = request.GET.get('app_id', None)
    version = request.GET.get('version', None)
    latest = request.GET.get('latest', None)
    include_multimedia = request.GET.get('include_multimedia', 'false').lower() == 'true'

    # Make sure URL params make sense
    if not app_id:
        return error("You must specify `app_id` in your GET parameters")
    if version and latest:
        return error("You can't specify both 'version' and 'latest'")
    if latest not in (None, 'release', 'build', 'save',):
        return error("latest must be either 'release', 'build', or 'save'")
    if version:
        try:
            version = int(version)
        except ValueError:
            return error("'version' must be an integer")

    try:
        app = get_app(app_id, version, latest)
        if not app:
            raise ResourceNotFound()
        app = app if isinstance(app, Document) else wrap_app(app)
    except (ResourceNotFound, DocTypeError):
        return error("Application not found", code=404)

    lang, langs = get_langs(request, app)

    with report_build_time(domain, app._id, 'live_preview'):
        return get_direct_ccz(domain, app, langs, version, include_multimedia)


def get_direct_ccz(domain, app, langs, version=None, include_multimedia=False, request=False):
    if not app.copy_of:
        errors = app.validate_app()
    else:
        errors = None

    if errors:
        error_html = render_to_string("app_manager/partials/build_errors.html", {
            'app': app,
            'build_errors': errors,
            'domain': domain,
            'langs': langs,
            'toggles': toggles_enabled_for_request(request),
        })
        return JsonResponse(
            {'error_html': error_html},
            status=400,
        )

    app.set_media_versions()
    download = FileDownload('application-{}-{}'.format(app.get_id, version))
    try:
        create_files_for_ccz(
            build=app,
            build_profile_id=None,
            include_multimedia_files=include_multimedia,
            download_id=download.download_id,
            compress_zip=True,
            filename='{}.ccz'.format(slugify(app.name)),
        )
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return FileDownload.get(download.download_id).toHttpResponse()
