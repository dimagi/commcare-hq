#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django import forms
from releasemanager.models import *
import datetime

class JarjadForm(forms.ModelForm):
    jar_file_upload = forms.FileField()
    jad_file_upload = forms.FileField()    
    
    class Meta:
        model = Jarjad
        exclude = ('jar_file', 'jad_file','uploaded_by','is_release')
           
        
class BuildForm(forms.ModelForm):
   class Meta:
       model = Build
       exclude = ('domain', 'is_release', 'created_at', 'jar_file', 'jad_file', 'zip_file')


class ResourceSetForm(forms.ModelForm):
    name = forms.SlugField(error_message="name should include only letters, numbers, underscores and hyphens")

    class Meta:
        model = ResourceSet
        exclude = ('domain', 'is_release', 'created_at')


