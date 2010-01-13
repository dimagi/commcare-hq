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
    view_name = forms.CharField(widget=forms.TextInput(attrs={'size':'40'}))
    def clean_view_name(self):
        if not re.match(r"^\w+$", self.cleaned_data["view_name"]):
            print "%s is invalid" % self.cleaned_data["view_name"]
            raise forms.ValidationError("View name can only contain numbers, letters, and underscores!")
        else: 
            print "%s is valid!!" % self.cleaned_data["view_name"]
        return self.cleaned_data["view_name"]
        
    class Meta:
        model = FormDataGroup
        fields = ("display_name", "view_name")
