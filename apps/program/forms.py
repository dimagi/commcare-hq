from django import forms 
from django.contrib.auth.models import User
from program.models import Program

class ProgramForm(forms.ModelForm):
    
    class Meta:
        model = Program
        exclude = ("domain", )


