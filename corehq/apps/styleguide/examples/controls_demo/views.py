from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop, ugettext as _
from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.style.decorators import use_select2
from corehq.apps.styleguide.examples.controls_demo.forms import (
    SelectControlDemoForm,
)
from dimagi.utils.decorators.memoized import memoized


class BaseControlDemoFormsView(BaseSectionPageView):
    section_name = ugettext_noop("Simple Crispy Form Example")

    def section_url(self):
        return reverse(DefaultControlsDemoFormsView.urlname)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseControlDemoFormsView, self).dispatch(request, *args, **kwargs)


class DefaultControlsDemoFormsView(BaseControlDemoFormsView):
    urlname = 'ex_controls_demo_default'

    def get(self, request, *args, **kwargs):
        # decide what to serve based on request
        return HttpResponseRedirect(reverse(SelectControlDemoView.urlname))


class SelectControlDemoView(BaseControlDemoFormsView):
    """This shows example usage for crispy forms in an HQ template view.
    """
    page_title = ugettext_noop("Using the Selects")
    urlname = 'ex_controls_demo'
    template_name = 'styleguide/examples/controls_demo/selects.html'

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(SelectControlDemoView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def controls_demo_form(self):
        initial_data = {}
        if self.request.method == 'POST':
            return SelectControlDemoForm(self.request.POST, initial=initial_data)
        return SelectControlDemoForm(initial=initial_data)

    @property
    def page_context(self):
        return {
            'controls_demo_form': self.controls_demo_form,
        }

    def post(self, request, *args, **kwargs):
        if self.controls_demo_form.is_valid():
            # do something to process the data
            # It's always best practice to give some sort of feedback to the
            # user that the form was successfully processed.
            messages.success(request,
                _("Form processed successfully.")
            )
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)
