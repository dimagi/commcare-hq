from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.styleguide.examples.bootstrap5.htmx_alpine_form_demo import FilterDemoForm
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class HtmxAlpineFormDemoView(HqHtmxActionMixin, BasePageView):
    urlname = 'sg_htmx_alpine_form_demo'
    template_name = 'styleguide/htmx_alpine_crispy/main.html'
    form_template = 'styleguide/htmx_alpine_crispy/partial_form.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    def form_context(self, existing_form=None, show_success=False):
        return {
            'filter_form': existing_form or FilterDemoForm(),
            'show_success': show_success,
        }

    @hq_hx_action('get')
    def load_form(self, request, *args, **kwargs):
        """
        HTMX action: load and render the initial form.
        """
        return self.render_htmx_partial_response(
            request,
            self.form_template,
            self.form_context(),
        )

    @hq_hx_action('post')
    def submit_form(self, request, *args, **kwargs):
        """
        HTMX action: handle form submission, validate, and
        re-render the form partial (with errors or success).
        """
        filter_form = FilterDemoForm(request.POST)
        show_success = False
        if filter_form.is_valid():
            # Do something with the form data here.
            show_success = True
            # Reset the form after successful submission.
            filter_form = None

        return self.render_htmx_partial_response(
            request,
            self.form_template,
            self.form_context(
                existing_form=filter_form,
                show_success=show_success,
            ),
        )
