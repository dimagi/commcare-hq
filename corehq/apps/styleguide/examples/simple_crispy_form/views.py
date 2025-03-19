from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from memoized import memoized

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.styleguide.examples.simple_crispy_form.forms import (
    ExampleUserLoginForm,
)


class BaseSimpleCrispyFormSectionView(BaseSectionPageView):
    section_name = gettext_noop("Simple Crispy Form Example")

    def section_url(self):
        return reverse(DefaultSimpleCrispyFormSectionView.urlname)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseSimpleCrispyFormSectionView, self).dispatch(request, *args, **kwargs)


class DefaultSimpleCrispyFormSectionView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_simple_crispy_forms_default'

    def get(self, request, *args, **kwargs):
        # decide what to serve based on request
        return HttpResponseRedirect(reverse(SimpleCrispyFormView.urlname))


class SimpleCrispyFormView(BaseSimpleCrispyFormSectionView):
    """This shows example usage for crispy forms in an HQ template view.
    """
    page_title = gettext_noop("Register a New User")
    urlname = 'ex_simple_crispy_forms'
    template_name = 'styleguide/bootstrap3/examples/simple_crispy_form/base.html'

    @property
    @memoized
    def simple_crispy_form(self):
        initial_data = {}
        if self.request.method == 'POST':
            return ExampleUserLoginForm(self.request.POST, initial=initial_data)
        return ExampleUserLoginForm(initial=initial_data)

    @property
    def page_context(self):
        return {
            'simple_crispy_form': self.simple_crispy_form,
        }

    def post(self, request, *args, **kwargs):
        if self.simple_crispy_form.is_valid():
            # do something to process the data
            # It's always best practice to give some sort of feedback to the
            # user that the form was successfully processed.
            messages.success(request,
                _("Form processed successfully.")
            )
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)
