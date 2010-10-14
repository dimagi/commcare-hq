# Create your views here.
from django.http import HttpResponse
from corehq.util.webutils import render_to_response
from corehq.apps.remote_apps.models import RemoteApp
from corehq.apps.new_xforms.models import Application

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