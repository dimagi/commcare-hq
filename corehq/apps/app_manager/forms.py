from django import forms

class NewXFormForm(forms.Form):
    """Potentially confusing name; HTML Form for creating/uploading a new xform"""
    name = forms.CharField(max_length=50)
    
class NewAppForm(forms.Form):
    name = forms.CharField(max_length=50)

class NewModuleForm(forms.Form):
    name = forms.CharField(max_length=50)

class ModuleConfigForm(forms.Form):
    pass