from django import forms
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

from corehq.apps.commtrack.models import Product, Program
from corehq.apps.commtrack.util import all_sms_codes
from corehq.apps.consumption.shortcuts import set_default_consumption_for_product, get_default_monthly_consumption
from django.core.urlresolvers import reverse
import json


class CurrencyField(forms.DecimalField):
    """
    Allows a field to accept human readable currency values.

    Example: $1,400.25 will be accepted and stored as 1400.25
    """
    def clean(self, value):
        for c in ['$', ',']:
            value = value.replace(c, '')

        return super(CurrencyField, self).clean(value)


class ProductForm(forms.Form):
    name = forms.CharField(max_length=100)
    code = forms.CharField(label=ugettext_noop("Product ID"), max_length=10, required=False)
    description = forms.CharField(max_length=500, required=False, widget=forms.Textarea)
    unit = forms.CharField(label=ugettext_noop("Units"), max_length=100, required=False)
    program_id = forms.ChoiceField(label=ugettext_noop("Program"), choices=(), required=True)
    cost = CurrencyField(max_digits=8, decimal_places=2, required=False)

    def __init__(self, product, *args, **kwargs):
        self.product = product

        kwargs['initial'] = self.product._doc
        kwargs['initial']['code'] = self.product.code

        super(ProductForm, self).__init__(*args, **kwargs)

        programs = Program.by_domain(self.product.domain, wrap=False)
        self.fields['program_id'].choices = tuple((prog['_id'], prog['name']) for prog in programs)

        # make sure to select default program if
        # this is a new product
        if not product._id:
            self.initial['program_id'] = Program.default_for_domain(
                self.product.domain
            )._id

    def clean_name(self):
        name = self.cleaned_data['name']

        other_products = [p for p in Product.by_domain(self.product.domain) if p._id != self.product._id]
        if name in [p.name for p in other_products]:
            raise forms.ValidationError('name already in use')

        return name

    def clean_code(self):
        code = self.cleaned_data['code'].lower()

        conflict = None
        sms_codes = all_sms_codes(self.product.domain)
        if code in sms_codes:
            conflict = sms_codes[code]
            if conflict[0] == 'product' and conflict[1]._id == self.product._id:
                conflict = None

        if conflict:
            conflict_name = {
                'product': lambda o: o.name,
                'action': lambda o: o.caption,
                'command': lambda o: o['caption'],
            }[conflict[0]](conflict[1])
            raise forms.ValidationError('product id not unique (conflicts with %s "%s")' % (conflict[0], conflict_name))

        return code.lower()

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError('form does not validate')

        product = instance or self.product

        for field in ('name', 'code', 'program_id', 'unit', 'description', 'cost'):
            setattr(product, field, self.cleaned_data[field])

        product_data = self.data.get('product_data')
        if product_data:
            product.product_data = json.loads(product_data)

        if commit:
            product.save()

        return product


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


class ProgramForm(forms.Form):
    name = forms.CharField(max_length=100)

    def __init__(self, program, *args, **kwargs):
        self.program = program

        kwargs['initial'] = self.program._doc
        super(ProgramForm, self).__init__(*args, **kwargs)

        # don't let users rename the uncategorized
        # program
        if program.default:
            self.fields['name'].required = False
            self.fields['name'].widget.attrs['readonly'] = True

    def clean_name(self):
        name = self.cleaned_data['name']

        other_program_names = [
            p['name'] for p in Program.by_domain(self.program.domain, wrap=False)
            if p['_id'] != self.program._id
        ]
        if name in other_program_names:
            raise forms.ValidationError(_('Name already in use'))

        return name

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError(_('Form does not validate'))

        program = instance or self.program

        setattr(program, 'name', self.cleaned_data['name'])

        if commit:
            program.save()

        return program
