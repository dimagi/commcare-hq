from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from jsonobject.exceptions import WrappingAttributeError
from corehq.apps.userreports.reports.view import ConfigurableReport
from corehq.apps.userreports.models import ReportConfiguration, IndicatorConfiguration
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.ui.forms import ConfigurableReportEditForm


@domain_admin_required
def edit_report(request, domain, report_id):
    try:
        config = ReportConfiguration.get(report_id)
        assert config.domain == domain
        assert config.doc_type == 'ReportConfiguration'
    except (ResourceNotFound, WrappingAttributeError, AssertionError):
        raise Http404()

    if request.method == 'POST':
        form = ConfigurableReportEditForm(domain, config, request.POST)
        if form.is_valid():
            for attr in (
                'config_id',
                'display_name',
                'description',
                'aggregation_columns',
                'filters',
                'columns'
            ):
                setattr(config, attr, form.cleaned_data[attr])
            try:
                ReportFactory.from_spec(config)
            except Exception, e:
                messages.error(request, _(u'Problem with report spec: {}').format(e))
            else:
                config.save()
                messages.success(request, _(u'Report {} saved!').format(config.display_name))
                return HttpResponseRedirect(reverse(ConfigurableReport.slug, args=[domain, config._id]))
    else:
        form = ConfigurableReportEditForm(domain, config)
    context = _shared_context(domain)
    context.update({
        'domain': domain,
        'form': form,
    })
    return render(request, "userreports/edit_report_config.html", context)


def _shared_context(domain):
    return {
        'reports': ReportConfiguration.by_domain(domain),
        'data_sources': IndicatorConfiguration.by_domain(domain),
    }