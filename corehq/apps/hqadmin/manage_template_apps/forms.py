from django import forms
from django.db.models import Value
from django.db.models.functions import Lower
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.app_manager.models import TemplateAppSector


class TemplateAppSectorForm(forms.ModelForm):

    class Meta:
        model = TemplateAppSector
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': gettext_lazy('For example, Agriculture'),
        })}

    def clean_name(self):
        name = self.cleaned_data['name']
        sectors = TemplateAppSector.objects.alias(normalized_name=Lower('name')).filter(
            normalized_name=Lower(Value(name))
        )
        if self.instance.pk:
            sectors = sectors.exclude(pk=self.instance.pk)
        if sectors.exists():
            raise forms.ValidationError(_('A sector with this name already exists.'), code='unique')
        return name
