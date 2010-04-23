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
        view_name = self.cleaned_data["view_name"]
        if not re.match(r"^\w+$", view_name):
            raise forms.ValidationError("View name can only contain numbers, letters, and underscores!")
        # check that the view name is unique... if it was changed.
        if self.instance.id:
            if FormDataGroup.objects.get(id=self.instance.id).view_name != view_name and \
               FormDataGroup.objects.filter(view_name=view_name).count() > 0:
                raise forms.ValidationError("Sorry, view name %s is already in use!  Please pick a new one." % view_name)
        return self.cleaned_data["view_name"]
        
    class Meta:
        model = FormDataGroup
        fields = ("display_name", "view_name")
