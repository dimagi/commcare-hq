from django.http import HttpResponse
from django.utils.translation import gettext_noop

from corehq.apps.styleguide.examples.simple_crispy_form.views import (
    BaseSimpleCrispyFormSectionView,
)


def default(request):
    return HttpResponse('woot')


class FormsSimpleCrispyFormExampleView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_simple_crispy_form_doc_forms'
    template_name = 'styleguide/bootstrap3/docs/simple_crispy_form/forms.html'
    page_title = gettext_noop("forms.py")


class ViewsSimpleCrispyFormExampleView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_simple_crispy_form_doc_views'
    template_name = 'styleguide/bootstrap3/docs/simple_crispy_form/views.html'
    page_title = gettext_noop("views.py")
