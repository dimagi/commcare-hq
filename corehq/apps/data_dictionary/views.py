from django.core.urlresolvers import reverse
from django.db.models.query import Prefetch
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _

from dimagi.utils.decorators.memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.data_dictionary import util
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.tabs.tabclasses import ApplicationsTab


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def generate_data_dictionary(request, domain):
    util.generate_data_dictionary(domain)
    return JsonResponse({"status": "success"})


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def data_dictionary_json(request, domain, case_type_name=None):
    props = []
    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name'))
    )
    if case_type_name:
        queryset = queryset.filter(name=case_type_name)
    for case_type in queryset:
        p = {
            "name": case_type.name,
            "properties": [],
        }
        for prop in case_type.properties.all():
            p['properties'].append({
                "description": prop.description,
                "name": prop.name,
                "type": prop.type,
            })
        props.append(p)
    return JsonResponse({'case_types': props})


class DataDictionaryView(BaseDomainView):
    section_name = _("Data Dictionary")
    template_name = "data_dictionary/base.html"
    urlname = 'data_dictionary'

    @method_decorator(login_and_domain_required)
    @toggles.DATA_DICTIONARY.required_decorator()
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
    @memoized
    def section_url(self):
        return reverse(DataDictionaryView.urlname, args=[self.domain])
