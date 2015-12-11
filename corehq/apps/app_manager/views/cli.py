from django.utils.text import slugify

from soil import DownloadBase
from corehq.apps.hqmedia.tasks import build_application_zip
from corehq.util.view_utils import absolute_reverse, json_error
from corehq.apps.domain.models import Domain
from dimagi.utils.web import json_response
from corehq.apps.domain.decorators import (
    login_or_digest_or_basic_or_apikey,
)
from corehq.apps.app_manager.dbaccessors import get_app


@json_error
@login_or_digest_or_basic_or_apikey()
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
    return json_response({
        'status': 'success',
        'applications': map(app_to_json, applications),
    })


@json_error
def direct_ccz(request, domain):
    if 'app_id' in request.GET:
        app = get_app(domain, request.GET['app_id'])
        app.set_media_versions(None)
        download = DownloadBase()
        build_application_zip(
            include_multimedia_files=False,
            include_index_files=True,
            app=app,
            download_id=download.download_id,
            compress_zip=True,
            filename='{}.ccz'.format(slugify(app.name)),
        )
        return DownloadBase.get(download.download_id).toHttpResponse()
    msg = "You must specify `app_id` in your GET parameters"
    return json_response({'status': 'error', 'message': msg}, status_code=400)
