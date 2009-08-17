#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django import forms
from buildmanager.models import *
import datetime

class BuildForm(forms.ModelForm):
    jar_file_upload = forms.FileField()
    jad_file_upload = forms.FileField()    
    
    class Meta:
        model = ProjectBuild
        exclude = ('jar_file', 'jad_file','jar_download_count','jad_download_count','uploaded_by','package_created')
           
        
