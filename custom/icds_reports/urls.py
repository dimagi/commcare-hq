from django.conf.urls import url

from custom.icds_reports.views import TableauView, DashboardView, IcdsDynamicTemplateView, ProgramSummaryView, \
    AwcOpenedView, PrevalenceOfUndernutritionView

urlpatterns = [
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', TableauView.as_view(), name='icds_tableau'),
    url(r'^icds_dashboard/', DashboardView.as_view(), name='icds_dashboard'),
    url(r'^icds-ng-template/(?P<template>[\w-].+)', IcdsDynamicTemplateView.as_view(), name='icds-ng-template'),
    url(r'^program_summary/(?P<step>[\w-]+)/', ProgramSummaryView.as_view(), name='program_summary'),
    url(r'^awc_opened/(?P<step>[\w-]+)/', AwcOpenedView.as_view(), name='awc_opened'),
    url(
        r'^underweight_children/(?P<step>[\w-]+)/',
        PrevalenceOfUndernutritionView.as_view(),
        name='underweight_children')
]
