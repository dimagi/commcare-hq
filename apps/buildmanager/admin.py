#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import datetime
import logging
import os
import re
import sys
import time
import datetime

import django
from buildmanager.models import *
from django.contrib import admin



class ProjectBuildInlineAdmin(admin.TabularInline):
    model = ProjectBuild
    extra = 5

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id','name','description','domain','num_builds')
    list_filter = ['domain',]
    #inlines = [ProjectBuildInlineAdmin]

class ProjectBuildAdmin(admin.ModelAdmin):
    list_display = ('id','build_number','project','revision_number',
                    'description','uploaded_by', "get_jar_download_count", 
                    "get_jad_download_count")
    list_filter = ['project','uploaded_by',]

admin.site.register(Project,ProjectAdmin)
admin.site.register(ProjectBuild,ProjectBuildAdmin)    
admin.site.register(BuildDownload)    
admin.site.register(BuildForm)    
