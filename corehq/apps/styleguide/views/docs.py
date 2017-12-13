from __future__ import absolute_import
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from corehq.apps.styleguide.examples.simple_crispy_form.views import \
    BaseSimpleCrispyFormSectionView


def default(request):
    return HttpResponse('woot')


class FormsSimpleCrispyFormExampleView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_simple_crispy_form_doc_forms'
    template_name = 'styleguide/docs/simple_crispy_form/forms.html'
    page_title = ugettext_noop("forms.py")


class ViewsSimpleCrispyFormExampleView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_simple_crispy_form_doc_views'
    template_name = 'styleguide/docs/simple_crispy_form/views.html'
    page_title = ugettext_noop("views.py")


class SelectControlFormExampleView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_controls_demo_doc_forms'
    template_name = 'styleguide/docs/controls_demo/forms.html'
    page_title = ugettext_noop("forms.py")


class SelectControlViewExampleView(BaseSimpleCrispyFormSectionView):
    urlname = 'ex_controls_demo_doc_views'
    template_name = 'styleguide/docs/controls_demo/views.html'
    page_title = ugettext_noop("views.py")
