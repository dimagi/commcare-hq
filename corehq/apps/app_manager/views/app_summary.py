from copy import copy

from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils.translation import ugettext_noop, ugettext_lazy as _
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation

from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.app_manager.xform import VELLUM_TYPES
from corehq.apps.domain.views import LoginAndDomainMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.reports.formdetails.readable import FormQuestionResponse
from corehq.apps.style.decorators import use_angular_js


class AppSummaryView(JSONResponseMixin, LoginAndDomainMixin, BasePageView, ApplicationViewMixin):
    urlname = 'app_summary'
    page_title = ugettext_noop("Summary")
    template_name = 'app_manager/summary.html'

    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        return super(AppSummaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(AppSummaryView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_context(self):
        if not self.app or self.app.doc_type == 'RemoteApp':
            raise Http404()

        form_name_map = {}
        for module in self.app.get_modules():
            for form in module.get_forms():
                form_name_map[form.unique_id] = {
                    'module_name': module.name,
                    'form_name': form.name
                }

        return {
            'VELLUM_TYPES': VELLUM_TYPES,
            'form_name_map': form_name_map,
            'langs': self.app.langs,
        }

    @property
    def parent_pages(self):
        return [
            {
                'title': _("Applications"),
                'url': reverse('view_app', args=[self.domain, self.app_id]),
            },
            {
                'title': self.app.name,
                'url': reverse('view_app', args=[self.domain, self.app_id]),
            }
        ]

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.app_id])

    @allow_remote_invocation
    def get_case_data(self, in_data):
        return {
            'response': self.app.get_case_metadata().to_json(),
            'success': True,
        }

    @allow_remote_invocation
    def get_form_data(self, in_data):
        modules = []
        errors = []
        for module in self.app.get_modules():
            forms = []
            module_meta = {
                'id': module.unique_id,
                'name': module.name,
                'short_comment': module.short_comment,
            }

            for form in module.get_forms():
                form_meta = {
                    'id': form.unique_id,
                    'name': form.name,
                    'short_comment': form.short_comment,
                }
                try:
                    questions = form.get_questions(
                        self.app.langs,
                        include_triggers=True,
                        include_groups=True,
                        include_translations=True
                    )
                    form_meta['questions'] = [FormQuestionResponse(q).to_json() for q in questions]
                except XFormException as e:
                    form_meta['error'] = {
                        'details': unicode(e),
                        'edit_url': reverse('form_source', args=[self.domain, self.app_id, module.id, form.id])
                    }
                    form_meta['module'] = copy(module_meta)
                    errors.append(form_meta)
                else:
                    forms.append(form_meta)

            module_meta['forms'] = forms
            modules.append(module_meta)
        return {
            'response': modules,
            'errors': errors,
            'success': True,
        }
