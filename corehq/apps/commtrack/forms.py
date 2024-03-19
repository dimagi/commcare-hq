from django import forms
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.utils.html import format_html

from crispy_forms.bootstrap import PrependedText
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Fieldset, Layout, Submit

from corehq.apps.consumption.shortcuts import (
    get_default_monthly_consumption,
    set_default_consumption_for_product,
)
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.products.models import SQLProduct


class CommTrackSettingsForm(forms.Form):
    use_auto_emergency_levels = forms.BooleanField(
        label=gettext_noop("Use default emergency levels"), required=False)

    stock_emergency_level = forms.DecimalField(
        label=gettext_lazy("Emergency Level (months)"), required=False)
    stock_understock_threshold = forms.DecimalField(
        label=gettext_lazy("Low Stock Level (months)"), required=False)
    stock_overstock_threshold = forms.DecimalField(
        label=gettext_lazy("Overstock Level (months)"), required=False)

    use_auto_consumption = forms.BooleanField(
        label=gettext_lazy("Use automatic consumption calculation"), required=False)
    consumption_min_transactions = forms.IntegerField(
        label=gettext_lazy("Minimum Transactions (Count)"), required=False)
    consumption_min_window = forms.IntegerField(
        label=gettext_lazy("Minimum Window for Calculation (Days)"), required=False)
    consumption_optimal_window = forms.IntegerField(
        label=gettext_lazy("Optimal Window for Calculation (Days)"), required=False)
    individual_consumption_defaults = forms.BooleanField(
        label=gettext_lazy("Configure consumption defaults individually by supply point"),
        required=False
    )

    sync_consumption_fixtures = forms.BooleanField(
        label=gettext_lazy("Sync consumption fixtures"), required=False)

    def clean(self):
        cleaned_data = super(CommTrackSettingsForm, self).clean()

        if cleaned_data.get('use_auto_consumption'):
            consumption_keys = [
                'consumption_min_transactions',
                'consumption_min_window',
                'consumption_optimal_window'
            ]

            for key in consumption_keys:
                if not cleaned_data.get(key):
                    self._errors[key] = self.error_class([_(
                        "You must use automatic consumption calculation or "
                        + " specify a value for all consumption settings."
                    )])

        return cleaned_data

    def __init__(self, *args, **kwargs):
        domain = kwargs.pop('domain')
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        self.helper.layout = Layout(
            Fieldset(
                _('Stock Levels'),
                'stock_emergency_level',
                'stock_understock_threshold',
                'stock_overstock_threshold'
            ),
            Fieldset(
                _('Consumption Settings'),
                PrependedText('use_auto_consumption', ''),
                'consumption_min_transactions',
                'consumption_min_window',
                'consumption_optimal_window',
                PrependedText('individual_consumption_defaults', ''),
            ),
            Fieldset(
                _('Phone Settings'),
                PrependedText('sync_consumption_fixtures', ''),
            ),
            hqcrispy.FormActions(
                ButtonHolder(
                    Submit('submit', gettext_lazy('Submit'))
                )
            )
        )

        from corehq.apps.locations.views import LocationImportView
        url = reverse(
            LocationImportView.urlname, args=[domain]
        )

        forms.Form.__init__(self, *args, **kwargs)

        self.fields['individual_consumption_defaults'].help_text = _(
            "This is configured by <a href='{url}'>bulk importing your organization structure</a>."
        ).format(url=url)


class ConsumptionForm(forms.Form):

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        super(ConsumptionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'form-label'

        layout = []
        products = SQLProduct.active_objects.filter(domain=domain)
        for product in products:
            field_name = 'default_%s' % product.product_id
            display = format_html(_('Default {product_name}'), product_name=product.name)
            layout.append(field_name)
            self.fields[field_name] = forms.DecimalField(
                label=display,
                required=False,
                initial=get_default_monthly_consumption(
                    self.domain,
                    product.product_id,
                    None,
                    None
                )
            )

        self.helper.layout = Layout(*layout)

    def save(self):
        for field in self.fields:
            val = self.cleaned_data[field]
            product = SQLProduct.objects.get(product_id=field.split('_')[1])
            assert product.domain == self.domain, 'Product {} attempted to be updated in domain {}'.format(
                product.product_id, self.domain
            )
            set_default_consumption_for_product(
                self.domain,
                product.product_id,
                val,
            )
