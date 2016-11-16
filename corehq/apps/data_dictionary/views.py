import json

from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _

from dimagi.utils.decorators.memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.data_dictionary import util
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.data_dictionary.models import CaseType
from corehq.tabs.tabclasses import ApplicationsTab


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def generate_data_dictionary(request, domain):
    util.generate_data_dictionary(domain)
    return JsonResponse({"status": "success"})


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def data_dictionary_json(request, domain):
    props = []
    queryset = CaseProperty.objects.filter(domain=domain).only(
        'description', 'case_type', 'property_name', 'type'
    )
    for prop in queryset:
        props.append({
            'description': prop.description,
            'case_type': prop.case_type,
            'property_name': prop.property_name,
            'type': prop.type,
        })
    return JsonResponse({'properties': props})


class DataDictionaryView(BaseDomainView):
    section_name = _("Data Dictionary")
    template_name = "data_dictionary/base.html"
    urlname = 'data_dictionary'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(DataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        main_context = super(DataDictionaryView, self).main_context
        main_context.update({
            'active_tab': ApplicationsTab(
                self.request,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            ),
        })
        return main_context

    @property
    def page_context(self):
        page_context = super(DataDictionaryView, self).page_context
        case_types = [
            c.name for c in CaseType.objects.filter(domain=self.request.domain).all()
        ]
        page_context.update({
            'case_types': case_types,
        })
        return page_context

    @property
    @memoized
    def section_url(self):
        return reverse(DataDictionaryView.urlname, args=[self.domain])
