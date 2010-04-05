#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.contrib import admin
from program.models import Program, ProgramMembership


class ProgramMembershipInline(admin.TabularInline):
    model = ProgramMembership

class ProgramAdmin(admin.ModelAdmin):
    model = Program
    inlines = [
        ProgramMembershipInline,
    ]    

admin.site.register(Program, ProgramAdmin)    
