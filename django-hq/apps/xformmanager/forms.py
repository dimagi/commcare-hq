from django import forms

# On this page, users can upload an xsd file from their laptop
# Then they get redirected to a page where they can download the xsd
class RegisterXForm(forms.Form):
    #title = forms.CharField(max_length=100)
    file  = forms.FileField()