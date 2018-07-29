from __future__ import absolute_import
from __future__ import unicode_literals
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms
from django.utils.translation import ugettext_noop


from corehq.apps.programs.models import Program
from corehq.apps.products.models import Product
from corehq.apps.commtrack.util import all_sms_codes
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
    code = forms.CharField(label=ugettext_noop("Product ID"), max_length=100, required=False)
    description = forms.CharField(max_length=500, required=False, widget=forms.Textarea)
    unit = forms.CharField(label=ugettext_noop("Units"), max_length=100, required=False)
    program_id = forms.ChoiceField(label=ugettext_noop("Program"), choices=(), required=True)
    cost = CurrencyField(max_digits=8, decimal_places=2, required=False)

    def __init__(self, product, *args, **kwargs):
        self.product = product

        kwargs['initial'] = self.product._doc
        kwargs['initial']['code'] = self.product.code

        super(ProductForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        programs = Program.by_domain(self.product.domain, wrap=False)
        self.fields['program_id'].choices = tuple((prog['_id'], prog['name']) for prog in programs)

        # make sure to select default program if
        # this is a new product
        if not product._id:
            self.initial['program_id'] = Program.default_for_domain(self.product.domain)._id

        self.helper.layout = Layout(
            'name',
            'code',
            'description',
            'unit',
            'program_id',
            'cost'
        )

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
