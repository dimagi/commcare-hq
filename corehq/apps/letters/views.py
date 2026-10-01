from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.app_manager.app_schemas.case_properties import all_case_properties_by_domain
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.letters.forms import LetterTemplateForm
from corehq.apps.letters.models import LetterTemplate
from corehq.apps.letters.rendering import LetterRenderError, render_preview
from corehq.apps.sms.views import BaseMessagingSectionView


@method_decorator(toggles.LETTER_TEMPLATES.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class LetterTemplateListView(BaseMessagingSectionView):
    urlname = 'letter_template_list'
    page_title = gettext_lazy('Letter Templates')
    template_name = 'letters/template_list.html'

    @property
    def page_context(self):
        return {'letter_templates': LetterTemplate.objects.filter(domain=self.domain).defer('body')}


@method_decorator(toggles.LETTER_TEMPLATES.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class LetterTemplateEditView(BaseMessagingSectionView):
    urlname = 'letter_template_edit'
    page_title = gettext_lazy('Edit Letter Template')
    template_name = 'letters/template_edit.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.kwargs['template_id']])

    @property
    def parent_pages(self):
        return [{
            'title': LetterTemplateListView.page_title,
            'url': reverse(LetterTemplateListView.urlname, args=[self.domain]),
        }]

    @cached_property
    def instance(self):
        return get_object_or_404(LetterTemplate, domain=self.domain, pk=self.kwargs['template_id'])

    @cached_property
    def form(self):
        return LetterTemplateForm(
            self.request.POST or None,
            instance=self.instance,
            preview_url=reverse(LetterTemplatePreviewView.urlname, args=[self.domain]),
        )

    @property
    def page_context(self):
        return {'form': self.form, 'ai_context': ai_context(self.domain)}

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            template = self.form.save(commit=False)
            template.domain = self.domain
            template.save()
            messages.success(request, _('Letter template saved.'))
            return HttpResponseRedirect(reverse(LetterTemplateListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class LetterTemplateCreateView(LetterTemplateEditView):
    urlname = 'letter_template_create'
    page_title = gettext_lazy('New Letter Template')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @cached_property
    def instance(self):
        return LetterTemplate(domain=self.domain)


@method_decorator(toggles.LETTER_TEMPLATES.required_decorator(), name='dispatch')
class LetterTemplateDeleteView(BaseMessagingSectionView):
    urlname = 'letter_template_delete'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        get_object_or_404(LetterTemplate, domain=self.domain, pk=kwargs['template_id']).delete()
        messages.success(request, _('Letter template deleted.'))
        return HttpResponseRedirect(reverse(LetterTemplateListView.urlname, args=[self.domain]))


@method_decorator(toggles.LETTER_TEMPLATES.required_decorator(), name='dispatch')
class LetterTemplatePreviewView(BaseMessagingSectionView):
    urlname = 'letter_template_preview'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        try:
            context = {'letter': render_preview(request.POST.get('body', ''))}
        except LetterRenderError as e:
            context = {'error': str(e)}
        return render(request, 'letters/preview.html', context)


def ai_context(domain):
    properties_by_case_type = sorted(
        (case_type, [p for p in props if '/' not in p])  # parent/* props aren't resolvable
        for case_type, props in all_case_properties_by_domain(domain).items()
        if case_type
    )
    return render_to_string('letters/ai_context.txt', {'properties_by_case_type': properties_by_case_type})
