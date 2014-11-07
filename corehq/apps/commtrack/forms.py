from django import forms
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

from corehq.apps.products.models import Product
from corehq.apps.consumption.shortcuts import set_default_consumption_for_product, get_default_monthly_consumption
from django.core.urlresolvers import reverse


class CommTrackSettingsForm(forms.Form):
    use_auto_emergency_levels = forms.BooleanField(
        label=ugettext_noop("Use default emergency levels"), required=False)

    stock_emergency_level = forms.DecimalField(
        label=ugettext_lazy("Emergency Level (months)"), required=False)
    stock_understock_threshold = forms.DecimalField(
        label=ugettext_lazy("Low Stock Level (months)"), required=False)
    stock_overstock_threshold = forms.DecimalField(
        label=ugettext_lazy("Overstock Level (months)"), required=False)

    use_auto_consumption = forms.BooleanField(
        label=ugettext_lazy("Use automatic consumption calculation"), required=False)
    consumption_min_transactions = forms.IntegerField(
        label=ugettext_lazy("Minimum Transactions (Count)"), required=False)
    consumption_min_window = forms.IntegerField(
        label=ugettext_lazy("Minimum Window for Calculation (Days)"), required=False)
    consumption_optimal_window = forms.IntegerField(
        label=ugettext_lazy("Optimal Window for Calculation (Days)"), required=False)
    individual_consumption_defaults = forms.BooleanField(
        label=ugettext_lazy("Configure consumption defaults individually by supply point"),
        required=False
    )

    sync_location_fixtures = forms.BooleanField(
        label=ugettext_lazy("Sync location fixtures"), required=False)

    sync_consumption_fixtures = forms.BooleanField(
        label=ugettext_lazy("Sync consumption fixtures"), required=False)

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
                        "You must use automatic consumption calculation or " +
                        " specify a value for all consumption settings."
                    )])

        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(
            Fieldset(
                _('Stock Levels'),
                'stock_emergency_level',
                'stock_understock_threshold',
                'stock_overstock_threshold'
            ),
            Fieldset(
                _('Consumption Settings'),
                'use_auto_consumption',
                'consumption_min_transactions',
                'consumption_min_window',
                'consumption_optimal_window',
                'individual_consumption_defaults',
            ),
            Fieldset(
                _('Phone Settings'),
                'sync_location_fixtures',
                'sync_consumption_fixtures',
            ),
            ButtonHolder(
                Submit('submit', ugettext_lazy('Submit'))
            )
        )

        from corehq.apps.locations.views import LocationImportView
        url = reverse(
            LocationImportView.urlname, args=[kwargs.pop('domain')]
        )

        forms.Form.__init__(self, *args, **kwargs)

        self.fields['individual_consumption_defaults'].help_text = _(
            "This is configured on the <a href='{url}'>bulk location import page</a>."
        ).format(url=url)


class ConsumptionForm(forms.Form):
    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        super(ConsumptionForm, self).__init__(*args, **kwargs)
        products = Product.by_domain(domain)
        for p in products:
            field_name = 'default_%s' % p._id
            display = _('Default %(product_name)s') % {'product_name': p.name}
            self.fields[field_name] = forms.DecimalField(
                label=display,
                required=False,
                initial=get_default_monthly_consumption(
                    self.domain,
                    p._id,
                    None,
                    None
                )
            )

    def save(self):
        for field in self.fields:
            val = self.cleaned_data[field]
            product = Product.get(field.split('_')[1])
            assert product.domain == self.domain, 'Product {} attempted to be updated in domain {}'.format(
                product._id, self.domain
            )
            set_default_consumption_for_product(
                self.domain,
                product._id,
                val,
            )
