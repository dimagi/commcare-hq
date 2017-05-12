from django.conf.urls import url

from custom.icds_reports.views import TableauView, DashboardView, IcdsDynamicTemplateView, ProgramSummaryView

urlpatterns = [
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', TableauView.as_view(), name='icds_tableau'),
    url(r'^icds_dashboard/', DashboardView.as_view(), name='icds_dashboard'),
    url(r'^icds-ng-template/(?P<template>[\w-].+)', IcdsDynamicTemplateView.as_view(), name='icds-ng-template'),
    url(r'^program_summary/(?P<step>[\w-]+)/', ProgramSummaryView.as_view(), name='program_summary')
]
