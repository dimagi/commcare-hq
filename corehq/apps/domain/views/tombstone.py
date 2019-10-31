from datetime import datetime

from crispy_forms import layout as crispy
from django.contrib import messages
from django.http import HttpResponseRedirect

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.crispy import FormActions, HQFormHelper

from django import forms
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqadmin.views import BaseAdminSectionView
from django.utils.translation import ugettext_lazy as _

from corehq.util import reverse


@method_decorator(require_superuser, name='dispatch')
class TombstoneManagement(BaseAdminSectionView):
    urlname = 'tombstone_management'
    page_title = _("Prevent the use of specific domain names")
    template_name = 'domain/tombstone_management.html'

    form = None
    domain_results = None

    def get_context_data(self, **kwargs):

        return {
            'form': self.form or TombstoneManagementForm(),
            'domains': self.domain_results or [],
        }

    def post(self, request, *args, **kwargs):
        self.form = TombstoneManagementForm(self.request.POST)
        if self.form.is_valid():
            domain_names = self.form.cleaned_data['domains']
            self.domain_results = []
            for domain in domain_names:
                project = Domain.get_by_name(domain)
                self.domain_results.append((domain, project))
        return self.get(request, *args, **kwargs)


@require_superuser
def create_tombstone(request):
    domain = request.POST.get('domain')
    project = Domain.get_by_name(domain)
    if project:
        messages.error(
            request,
            "Could not create tombstone for {} because that domain already exists"
            .format(domain))
    else:
        project = Domain(
            name=domain,
            hr_name='{} (Created as a tombstone)'.format(domain),
            is_active=False,
            date_created=datetime.utcnow(),
            creating_user=request.couch_user.username,
            secure_submissions=True,
            use_sql_backend=True,
            first_domain_for_user=False,
            is_tombstone=True,
        )
        project.save()
        messages.success(request, "Successfully created a tombstone for {}".format(domain))
    return HttpResponseRedirect(reverse(TombstoneManagement.urlname))


class TombstoneManagementForm(forms.Form):
    csv_domain_list = forms.CharField(
        label="Comma separated domains",
        widget=forms.Textarea()
    )

    @staticmethod
    def split_csv(comma_separated_list):
        return list(
            filter(None, (domain.strip() for domain in comma_separated_list.split(','))))

    def clean(self):
        csv_domain_list = self.cleaned_data.get('csv_domain_list', '')
        self.cleaned_data['domains'] = self.split_csv(csv_domain_list)
        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'csv_domain_list',
            FormActions(
                crispy.Submit(
                    '',
                    'Check Domains'
                )
            )
        )
