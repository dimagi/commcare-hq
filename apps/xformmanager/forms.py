from django import forms
from models import FormDataGroup
import re

# On this page, users can upload an xsd file from their laptop
# Then they get redirected to a page where they can download the xsd
class RegisterXForm(forms.Form):
    file  = forms.FileField()
    form_display_name= forms.CharField(max_length=128, label=u'Form Display Name')
    
class SubmitDataForm(forms.Form):
    file  = forms.FileField()


class FormDataGroupForm(forms.ModelForm):
    """Form for basic form group data""" 
    display_name = forms.CharField(widget=forms.TextInput(attrs={'size':'80'}))
        
    class Meta:
        model = FormDataGroup
        fields = ("display_name",)
