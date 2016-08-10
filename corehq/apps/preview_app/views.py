from django.views.generic.base import TemplateView
from django.conf import settings

from corehq.apps.app_manager.dbaccessors import get_app


class PreviewAppView(TemplateView):
    template_name = 'preview_app/base.html'
    urlname = 'preview_app'

    def get(self, request, *args, **kwargs):
        app = get_app(request.domain, kwargs.pop('app_id'))
        return self.render_to_response({
            'app': app,
            'formplayer_url': settings.FORMPLAYER_URL,
        })
