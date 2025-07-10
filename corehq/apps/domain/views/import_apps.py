import json

from django.http import HttpResponse
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator

from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action

from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.app_manager.models import import_app as import_app_util
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.forms import ConstructAppDownloadLinkForm, ImportAppForm
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5


@method_decorator(
    [
        use_bootstrap5,
        require_can_edit_apps,
    ],
    name='dispatch',
)
class ImportAppStepsView(LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = 'import_app_steps'
    template_name = 'hqwebapp/crispy/next_action_form.html'
    container_id = 'import-app-steps'

    def get_context_data(self, form=None, next_action=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form': form or ConstructAppDownloadLinkForm(),
            'container_id': self.container_id,
            'next_action': next_action or 'process_first_step',
        })
        return context

    @hq_hx_action('post')
    def process_first_step(self, request, *args, **kwargs):
        form = ConstructAppDownloadLinkForm(request.POST)
        next_action = 'process_first_step'
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
            next_action = 'process_second_step'
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    @hq_hx_action('post')
    def process_second_step(self, request, *args, **kwargs):
        from corehq.apps.app_manager.views.apps import clear_app_cache
        from corehq.apps.app_manager.views.utils import back_to_main

        form = ImportAppForm(
            self.container_id,
            cancel_url=request.path_info,
            data=request.POST,
            files=request.FILES
        )

        next_action = 'process_second_step'

        if form.is_valid():
            clear_app_cache(request, self.domain)
            name = form.cleaned_data.get('app_name')
            file = form.cleaned_data.get('app_file')
            source = json.load(file)
            app = import_app_util(source, self.domain, {'name': name}, request=request)
            response = back_to_main(request, self.domain, app_id=app._id)
            if request.headers.get('HX-Request'):
                # Add a header to tell HTMX to do a full page redirect
                return HttpResponse(
                    status=200,
                    headers={'HX-Redirect': response.url}
                )
            return response
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)
