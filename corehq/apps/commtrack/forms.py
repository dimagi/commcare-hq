from __future__ import absolute_import
from __future__ import unicode_literals
from crispy_forms.bootstrap import PrependedText
from django import forms
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, HTML

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.forms import FormListForm
from corehq.apps.products.models import Product
from corehq.apps.consumption.shortcuts import set_default_consumption_for_product, get_default_monthly_consumption
from corehq.toggles import LOCATION_TYPE_STOCK_RATES
from django.urls import reverse


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
        from .views import StockLevelsView
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
            ) if not LOCATION_TYPE_STOCK_RATES.enabled(domain) else Fieldset(
                _('Stock Levels'),
                ButtonHolder(
                    HTML('<a href="{}" class="btn btn-primary">{}</a>'.format(
                        reverse(StockLevelsView.urlname, args=[domain]),
                        _('Configure Stock Levels')))),
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
                    Submit('submit', ugettext_lazy('Submit'))
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
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        layout = []
        products = Product.by_domain(domain)
        for p in products:
            field_name = 'default_%s' % p._id
            display = _('Default %(product_name)s') % {'product_name': p.name}
            layout.append(field_name)
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

        layout.append(hqcrispy.FormActions(
            ButtonHolder(
                Submit('submit', ugettext_lazy('Update Default Consumption Info'))
            )
        ))
        self.helper.layout = Layout(*layout)

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


class LocationTypeStockLevels(forms.Form):
    """
    Sub form for configuring stock levels for a specific location type
    """
    emergency_level = forms.DecimalField(
        label=ugettext_noop("Emergency Level (months)"),
        required=True,
    )
    understock_threshold = forms.DecimalField(
        label=ugettext_noop("Low Stock Level (months)"),
        required=True,
    )
    overstock_threshold = forms.DecimalField(
        label=ugettext_noop("Overstock Level (months)"),
        required=True,
    )

    def clean(self):
        cleaned_data = super(LocationTypeStockLevels, self).clean()
        emergency = cleaned_data.get('emergency_level')
        understock = cleaned_data.get('understock_threshold')
        overstock = cleaned_data.get('overstock_threshold')
        if not self.errors and not (emergency < understock < overstock):
            raise forms.ValidationError(_(
                "The Emergency Level must be less than the Low Stock Level, "
                "which much must be less than the Overstock Level."
            ))
        return cleaned_data


class StockLevelsForm(FormListForm):
    """
    Form for specifying stock levels per location type
    """

    child_form_class = LocationTypeStockLevels
    columns = [
        {'label': _("Location Type"), 'key': 'loc_type'},
        'emergency_level',
        'understock_threshold',
        'overstock_threshold',
    ]
