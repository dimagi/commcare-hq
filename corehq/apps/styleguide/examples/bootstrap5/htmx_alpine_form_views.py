from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.styleguide.examples.bootstrap5.htmx_alpine_form_demo import FilterDemoForm


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class HtmxAlpineFormDemoView(BasePageView):
    """
    This view is just a basic page view which acts as the "container" for a separate
    "FilterDemoFormView" that handles the interaction with the "FilterDemoForm".

    This establishes the page as a `js_entry` point for HTMX + Alpine and loads the
    form view below asynchronously in the page content.
    """
    urlname = "sg_htmx_alpine_form_demo"
    template_name = "styleguide/htmx_alpine_crispy/main.html"

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            "filter_form_url": reverse(FilterDemoFormView.urlname),
        }


# don't forget to add the same security decorators as the "host" view above!
@method_decorator(login_required, name='dispatch')
# the use_bootstrap5 decorator is needed here for crispy forms to work properly
@method_decorator(use_bootstrap5, name='dispatch')
class FilterDemoFormView(TemplateView):
    """
    This view inherits from a simple `TemplateView` because the `template_name` is a
    partial HTML template, so we don't need to extend any of the base HQ templates.
    """
    urlname = "sg_htmx_alpine_filter_form"
    template_name = "styleguide/htmx_alpine_crispy/partial_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = kwargs.pop('filter_form') if 'filter_form' in kwargs else None
        context.update({
            "filter_form": filter_form or FilterDemoForm(),
        })
        return context

    def post(self, request, *args, **kwargs):
        filter_form = FilterDemoForm(request.POST)
        show_success = False
        if filter_form.is_valid():
            # do something with filter form data
            show_success = True
            filter_form = None
        return super().get(
            request,
            filter_form=filter_form,
            show_success=show_success,
            *args,
            **kwargs
        )
