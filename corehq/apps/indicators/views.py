import json
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop, ugettext as _
from django.views.generic import TemplateView, View
from tastypie.http import HttpBadRequest
from corehq.apps.crud.views import BaseCRUDFormView
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.indicators.admin.crud import IndicatorCRUDFormRequestManager
from corehq.apps.indicators.admin.forms import BulkCopyIndicatorsForm
from corehq.apps.indicators.dispatcher import require_edit_indicators
from corehq.apps.indicators.forms import ImportIndicatorsFromJsonFileForm
from corehq.apps.indicators.models import (
    IndicatorDefinition,
    DynamicIndicatorDefinition,
)
from corehq.apps.indicators.utils import get_indicator_domains, get_namespaces
from corehq.apps.style.decorators import use_multiselect
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function


@require_edit_indicators
@login_and_domain_required
def default_admin(request, domain, template="reports/base_template.html", **kwargs):
    if request.domain not in get_indicator_domains():
        raise Http404
    request.use_jquery_ui = True
    request.use_datatables = True
    from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
    context = dict(
        domain=domain,
        project=domain,
        report=dict(
            title="Select an Indicator Definition Type",
            show=True,
            slug=None,
            is_async=True,
            section_name=BaseIndicatorAdminInterface.section_name,
        )
    )
    return render(request, template, context)


class IndicatorAdminCRUDFormView(BaseCRUDFormView):
    base_loc = "corehq.apps.indicators.admin.forms"
    template_name = "indicators/forms/crud.add_indicator.html"
    form_request_manager = IndicatorCRUDFormRequestManager

    @method_decorator(require_edit_indicators)
    def dispatch(self, request, *args, **kwargs):
        return super(IndicatorAdminCRUDFormView, self).dispatch(request, *args, **kwargs)


class BulkCopyIndicatorsView(TemplateView):
    indicator_loc = "corehq.apps.indicators.models"
    template_name = "indicators/forms/copy_to_domain.html"

    @method_decorator(require_edit_indicators)
    @use_multiselect
    def dispatch(self, request, domain, indicator_type=None, *args, **kwargs):
        self.domain = domain
        try:
            self.indicator_class = to_function("%s.%s" % (self.indicator_loc, indicator_type))
        except AttributeError:
            return HttpBadRequest("%s.%s does not exist" % (self.indicator_loc, indicator_type))

        status = {}

        if request.method == 'POST':
            form = BulkCopyIndicatorsForm(data=request.POST, domain=self.domain,
                                          couch_user=request.couch_user, indicator_class=self.indicator_class)
            if form.is_valid():
                status = form.copy_indicators()
        else:
            form = BulkCopyIndicatorsForm(domain=self.domain,
                                          couch_user=request.couch_user, indicator_class=self.indicator_class)

        return render(request, self.template_name, {
            "form": form,
            "status": status,
            "domain": self.domain,
            "indicator_type": self.indicator_class.__name__,
            "indicator_name": self.indicator_class.get_nice_name(),
        })


class BulkExportIndicatorsView(View):
    urlname = 'indicators_bulk_export'

    @method_decorator(require_edit_indicators)
    def dispatch(self, request, *args, **kwargs):
        return super(BulkExportIndicatorsView, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        namespaces = get_namespaces(domain)
        db = IndicatorDefinition.get_db()

        def _clean_indicator(doc):
            del doc['_id']
            del doc['_rev']
            del doc['domain']
            return doc

        data = {}
        for view_type in [
            'indicator_definitions',
            'dynamic_indicator_definitions',
        ]:
            data[view_type] = []
            for namespace in namespaces:
                key = ["type", namespace, domain]
                result = db.view(
                    'indicators/%s' % view_type,
                    reduce=False,
                    startkey=key,
                    endkey=key+[{}],
                    include_docs=True,
                ).all()
                data[view_type].extend([_clean_indicator(d['doc']) for d in result])

        response = HttpResponse(json.dumps(data), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=%(domain)s-indicators.json' % {
            'domain': domain,
        }
        return response


class BulkImportIndicatorsView(BaseSectionPageView, DomainViewMixin):
    urlname = 'indicators_upload_bulk'
    section_name = ugettext_noop("Administer Indicators")
    page_title = ugettext_noop("Bulk Import Indicators")
    template_name = 'indicators/bulk_import.html'

    @method_decorator(login_and_domain_required)
    @method_decorator(require_edit_indicators)
    def dispatch(self, request, *args, **kwargs):
        return super(BulkImportIndicatorsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def import_form(self):
        if self.request.method == 'POST':
            return ImportIndicatorsFromJsonFileForm(self.request.POST)
        return ImportIndicatorsFromJsonFileForm()

    @property
    def page_context(self):
        return {
            'import_form': self.import_form,
            'domain': self.domain,
        }

    @property
    def section_url(self):
        return reverse('default_indicator_admin', args=[self.domain])

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('json_file')
        if upload and self.import_form.is_valid():
            data = json.loads(upload.read())
            for (view_type, indicator_class) in [
                (u'indicator_definitions', IndicatorDefinition),
                (u'dynamic_indicator_definitions', DynamicIndicatorDefinition),
            ]:
                for doc in data[view_type]:
                    copied = indicator_class.copy_to_domain(
                        self.domain, doc,
                        override=self.import_form.cleaned_data['override_existing']
                    )
            messages.success(
                request,
                _("Imported indicators!")
            )
            return HttpResponseRedirect(self.page_url)
        messages.error(
            request,
            _("Failed up import any indicators. Check your file.")
        )
        return self.get(request, *args, **kwargs)
