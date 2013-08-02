from django import forms

class EmailForm(forms.Form):
    email_subject = forms.CharField(max_length=100)
    email_body = forms.CharField()
