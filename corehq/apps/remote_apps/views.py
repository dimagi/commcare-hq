# Create your views here.
from corehq.util.webutils import render_to_response
import corehq
from corehq.apps.app_manager.models import RemoteApp

def view(req, domain, template="remote_apps/apps.html"):
    apps = RemoteApp.view('remote_apps/by_domain').all()
    return render_to_response(req, template, {
        'applications': apps,
        'domain': domain
    })

def app_view(req, domain, app_id, template="remote_apps/apps.html"):
    app = RemoteApp.get_app(domain, app_id)
    apps = RemoteApp.view('remote_apps/by_domain').all()

    return render_to_response(req, template, {
        'applications': apps,
        'domain': domain,
        'app': app
    })


def download_jad(req, domain, app_id):
    return corehq.apps.new_xforms.views.download_jad(req, domain, app_id)