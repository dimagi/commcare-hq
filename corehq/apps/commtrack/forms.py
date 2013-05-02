from django import forms
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.util import all_sms_codes

class ProductForm(forms.Form):
    name = forms.CharField(max_length=100)
    code = forms.CharField(label='SMS Code', max_length=10)
    description = forms.CharField(max_length=500, required=False)
    category = forms.CharField(max_length=100, required=False)

    def __init__(self, product, *args, **kwargs):
        self.product = product
        kwargs['initial'] = self.product._doc
        super(ProductForm, self).__init__(*args, **kwargs)

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
            raise forms.ValidationError('sms code not unique (conflicts with %s "%s")' % (conflict[0], conflict_name))

        return code.lower()

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError('form does not validate')

        product = instance or self.product

        for field in ('name', 'code', 'category', 'description'):
            setattr(product, field, self.cleaned_data[field])

        if commit:
            product.save()

        return product
