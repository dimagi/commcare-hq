from __future__ import absolute_import
from django.conf.urls import url

from custom.icds_reports.views import TableauView, DashboardView, IcdsDynamicTemplateView, ProgramSummaryView, \
    PrevalenceOfUndernutritionView, LocationView, LocationAncestorsView, AwcReportsView, \
    ExportIndicatorView, FactSheetsView, PrevalenceOfSevereView, PrevalenceOfStuntingView, \
    ExclusiveBreastfeedingView, NewbornsWithLowBirthWeightView, EarlyInitiationBreastfeeding, \
    ChildrenInitiatedView, InstitutionalDeliveriesView, ImmunizationCoverageView, AWCDailyStatusView, \
    AWCsCoveredView, RegisteredHouseholdView, EnrolledChildrenView, EnrolledWomenView, \
    LactatingEnrolledWomenView, AdolescentGirlsView, AdhaarBeneficiariesView, CleanWaterView, \
    FunctionalToiletView, MedicineKitView, InfantsWeightScaleView, AdultWeightScaleView, AggregationScriptPage, \
    ICDSBugReportView, AWCLocationView, DownloadPDFReport, CheckPDFReportStatus

urlpatterns = [
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', TableauView.as_view(), name='icds_tableau'),
    url(r'^icds_dashboard/', DashboardView.as_view(), name='icds_dashboard'),
    url(r'^icds-ng-template/(?P<template>[\w-].+)', IcdsDynamicTemplateView.as_view(), name='icds-ng-template'),
    url(r'^program_summary/(?P<step>[\w-]+)/', ProgramSummaryView.as_view(), name='program_summary'),
    url(r'^awc_reports/(?P<step>[\w-]+)/', AwcReportsView.as_view(), name='awc_reports'),
    url(
        r'^underweight_children/(?P<step>[\w-]+)/',
        PrevalenceOfUndernutritionView.as_view(),
        name='underweight_children'),
    url(
        r'^prevalence_of_severe/(?P<step>[\w-]+)/',
        PrevalenceOfSevereView.as_view(),
        name='prevalence_of_severe'),
    url(
        r'^prevalence_of_stunting/(?P<step>[\w-]+)/',
        PrevalenceOfStuntingView.as_view(),
        name='prevalence_of_stunting'),
    url(
        r'^low_birth/(?P<step>[\w-]+)/',
        NewbornsWithLowBirthWeightView.as_view(),
        name='low_birth'),
    url(
        r'^early_initiation/(?P<step>[\w-]+)/',
        EarlyInitiationBreastfeeding.as_view(),
        name='early_initiation'),
    url(r'^locations$', LocationView.as_view(), name='icds_locations'),
    url(r'^locations/ancestors$', LocationAncestorsView.as_view(), name='icds_locations_ancestors'),
    url(r'^export_indicator$', ExportIndicatorView.as_view(), name='icds_export_indicator'),
    url(r'^fact_sheets$', FactSheetsView.as_view(), name='fact_sheets'),
    url(
        r'^exclusive-breastfeeding/(?P<step>[\w-]+)/',
        ExclusiveBreastfeedingView.as_view(),
        name='exclusive-breastfeeding'),
    url(
        r'^children_initiated/(?P<step>[\w-]+)/',
        ChildrenInitiatedView.as_view(),
        name='children_initiated'),
    url(
        r'^institutional_deliveries/(?P<step>[\w-]+)/',
        InstitutionalDeliveriesView.as_view(),
        name='institutional_deliveries'),
    url(
        r'^immunization_coverage/(?P<step>[\w-]+)/',
        ImmunizationCoverageView.as_view(),
        name='immunization_coverage'),
    url(
        r'^awc_daily_status/(?P<step>[\w-]+)/',
        AWCDailyStatusView.as_view(),
        name='awc_daily_status'),
    url(
        r'^awcs_covered/(?P<step>[\w-]+)/',
        AWCsCoveredView.as_view(),
        name='awcs_covered'),
    url(
        r'^registered_household/(?P<step>[\w-]+)/',
        RegisteredHouseholdView.as_view(),
        name='registered_household'),
    url(
        r'^enrolled_children/(?P<step>[\w-]+)/',
        EnrolledChildrenView.as_view(),
        name='enrolled_children'),
    url(
        r'^enrolled_women/(?P<step>[\w-]+)/',
        EnrolledWomenView.as_view(),
        name='enrolled_women'),
    url(
        r'^lactating_enrolled_women/(?P<step>[\w-]+)/',
        LactatingEnrolledWomenView.as_view(),
        name='lactating_enrolled_women'),
    url(
        r'^adolescent_girls/(?P<step>[\w-]+)/',
        AdolescentGirlsView.as_view(),
        name='adolescent_girls'),
    url(
        r'^adhaar/(?P<step>[\w-]+)/',
        AdhaarBeneficiariesView.as_view(),
        name='adhaar'),
    url(
        r'^clean_water/(?P<step>[\w-]+)/',
        CleanWaterView.as_view(),
        name='clean_water'),
    url(
        r'^functional_toilet/(?P<step>[\w-]+)/',
        FunctionalToiletView.as_view(),
        name='functional_toilet'),
    url(
        r'^medicine_kit/(?P<step>[\w-]+)/',
        MedicineKitView.as_view(),
        name='medicine_kit'),
    url(
        r'^infants_weight_scale/(?P<step>[\w-]+)/',
        InfantsWeightScaleView.as_view(),
        name='infants_weight_scale'),
    url(
        r'^adult_weight_scale/(?P<step>[\w-]+)/',
        AdultWeightScaleView.as_view(),
        name='adult_weight_scale'),
    url(r'^aggregation_script/', AggregationScriptPage.as_view(), name=AggregationScriptPage.urlname),
    url(r'^bug_report/', ICDSBugReportView.as_view(), name='icds_bug_report'),
    url(r'^awc_locations/', AWCLocationView.as_view(), name='awc_locations'),
    url(r'^download_pdf/', DownloadPDFReport.as_view(), name='icds_download_pdf'),
    url(r'^issnip_pdf_status/', CheckPDFReportStatus.as_view(), name='issnip_pdf_status')
]
