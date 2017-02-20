from django import forms
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.es.users import UserES
from corehq.apps.style import crispy as hqcrispy
from corehq.apps.style.decorators import use_select2

from custom.icds.messaging.indicators import (
    AWWSubmissionPerformanceIndicator,
    LSSubmissionPerformanceIndicator,
    LSVHNDSurveyIndicator,
)
from custom.icds.tasks import run_indicator


class IndicatorTestForm(forms.Form):

    users = forms.CharField(
        help_text=ugettext_lazy("Type a username")
    )
    indicator = forms.ChoiceField(
        label=ugettext_lazy("Indicator"),
        choices=(
            ('aww_sub_perf', 'AWW Submission Performance'),
            ('ls_sub_perf', 'LS SubmissionPerformance'),
            ('ls_vhnd_survey', 'LS VHND Survey'),
        ),
        required=True
    )

    def __init__(self, *args, **kwargs):
        domain = kwargs.pop('domain')
        super(IndicatorTestForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = reverse('sms_indicators', args=[domain])
        self.helper.form_class = "form form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-10 col-md-10 col-lg-10'
        self.helper.layout = crispy.Layout(
            crispy.Field('users', css_class='sms-typeahead'),
            crispy.Field('indicator'),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Test"),
                    type="submit",
                    css_class="btn-primary",
                ),
            ),
        )


class IndicatorTestPage(BaseDomainView):
    template_name = 'icds/messaging/indicators/test_indicators.html'
    urlname = 'sms_indicators'
    page_title = _('Test ICDS SMS indicators')
    section_url = ""
    form_class = IndicatorTestForm

    @property
    def page_context(self):
        page_context = super(IndicatorTestPage, self).page_context
        page_context.update({
            'form': IndicatorTestForm(domain=self.domain)
        })
        return page_context

    @method_decorator(require_superuser_or_developer)
    @use_select2
    def dispatch(self, *args, **kwargs):
        return super(IndicatorTestPage, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, domain=request.domain)
        if form.is_valid():
            user_id = request.POST['users']
            indicator = request.POST['indicator']
            indicator_cls = get_indicator_class(indicator)
            run_indicator.delay(request.domain, user_id, indicator_cls)

        return render(request, self.template_name, {'form': form})


def get_indicator_class(slug):
    return {
        'aww_sub_perf': AWWSubmissionPerformanceIndicator,
        'ls_sub_perf': LSSubmissionPerformanceIndicator,
        'ls_vhnd_survey': LSVHNDSurveyIndicator,
    }[slug]


@require_superuser_or_developer
def user_lookup(request, domain):
    return JsonResponse({
        'results': (
            UserES()
            .domain(domain)
            .fields(['_id', 'base_username'])
            .search_string_query(request.GET['term'])
            .size(10)
            .run().hits)
    })
