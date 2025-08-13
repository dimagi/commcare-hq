import json

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.app_manager.models import import_app as import_app_util
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.forms import ExtractAppInfoForm, ImportAppForm
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.hqmedia.views import BulkUploadMultimediaView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action

SERVER_SUBDOMAIN_MAPPING = {
    'production': 'www',
    'india': 'india',
    'eu': 'eu',
}


@method_decorator(
    [
        use_bootstrap5,
        require_can_edit_apps,
    ],
    name='dispatch',
)
class ImportAppStepsView(LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = 'import_app_steps'
    template_name = 'hqwebapp/htmx/forms/next_action_form.html'
    container_id = 'import-app-steps'

    def get_context_data(self, form=None, next_action=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form': form or ExtractAppInfoForm(),
            'container_id': self.container_id,
            'next_action': next_action or 'extract_app_info_from_url',
        })
        return context

    @hq_hx_action('post')
    def extract_app_info_from_url(self, request, *args, **kwargs):
        form = ExtractAppInfoForm(request.POST)
        next_action = 'extract_app_info_from_url'
        if form.is_valid():
            # Store the validated data for use in the second step
            validated_data = {
                'source_server': form.cleaned_data['source_server'],
                'source_domain': form.cleaned_data['source_domain'],
                'app_id': form.cleaned_data['app_id'],
            }
            form = ImportAppForm(
                self.container_id,
                cancel_url=request.path_info,
                validated_data=validated_data
            )
            next_action = 'import_app'
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    @hq_hx_action('post')
    def import_app(self, request, *args, **kwargs):
        from corehq.apps.app_manager.views.apps import clear_app_cache

        form = ImportAppForm(
            self.container_id,
            cancel_url=request.path_info,
            data=request.POST,
            files=request.FILES
        )

        next_action = 'import_app'

        if form.is_valid():
            clear_app_cache(request, self.domain)
            name = form.cleaned_data.get('app_name')
            file = form.cleaned_data.get('app_file')
            file.seek(0)  # rewind to the beginning becaues the file has already been read once when validating
            source = json.load(file)
            app = import_app_util(source, self.domain, {'name': name}, request=request)
            source_server = form.cleaned_data.get('source_server')
            source_domain = form.cleaned_data.get('source_domain')
            source_app_id = form.cleaned_data.get('app_id')
            new_app_id = app._id
            response = self.render_import_multimedia_instructions(request, source_server, source_domain,
                                                                  source_app_id, new_app_id)
            response["HX-Push-Url"] = self._add_params_to_url(
                source_server, source_domain, source_app_id, new_app_id
            )
            return response
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    def _add_params_to_url(self, source_server, source_domain, source_app_id, new_app_id):
        # Add query params to the url so user won't lost the instruction page if refresh the page accidentally
        from corehq.apps.domain.views.settings import ImportAppFromAnotherServerView
        current_url = reverse(ImportAppFromAnotherServerView.urlname, args=[self.domain])
        query_params = (
            f"?source_server={source_server}&source_domain={source_domain}&"
            f"source_app_id={source_app_id}&new_app_id={new_app_id}"
        )
        return current_url + query_params

    def render_import_multimedia_instructions(self, request, source_server, source_domain, source_app_id,
                                              new_app_id):
        from corehq.apps.app_manager.views.utils import back_to_main
        source_multimedia_url = (
            f"https://{SERVER_SUBDOMAIN_MAPPING[source_server]}.commcarehq.org/a/"
            f"{source_domain}/apps/view/{source_app_id}/settings/#multimedia-tab"
        )
        current_multimedia_url = reverse(BulkUploadMultimediaView.urlname, args=[self.domain, new_app_id])
        new_app_url = back_to_main(request, self.domain, new_app_id).url
        return self.render_htmx_partial_response(request, 'domain/partials/how_to_import_multimedia.html', {
            'source_multimedia_url': source_multimedia_url,
            'current_multimedia_url': current_multimedia_url,
            'new_app_url': new_app_url,
        })

    @hq_hx_action('get')
    def get_instructions(self, request, *args, **kwargs):
        source_server = request.GET.get('source_server')
        source_domain = request.GET.get('source_domain')
        source_app_id = request.GET.get('source_app_id')
        new_app_id = request.GET.get('new_app_id')
        return self.render_import_multimedia_instructions(request, source_server, source_domain, source_app_id,
                                                          new_app_id)
