from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from custom.icds_reports.views import TableauView, DashboardView, IcdsDynamicTemplateView, ProgramSummaryView, \
    PrevalenceOfUndernutritionView, LocationView, LocationAncestorsView, AwcReportsView, \
    ExportIndicatorView, FactSheetsView, PrevalenceOfSevereView, PrevalenceOfStuntingView, \
    ExclusiveBreastfeedingView, NewbornsWithLowBirthWeightView, EarlyInitiationBreastfeeding, \
    ChildrenInitiatedView, InstitutionalDeliveriesView, ImmunizationCoverageView, AWCDailyStatusView, \
    AWCsCoveredView, RegisteredHouseholdView, EnrolledChildrenView, EnrolledWomenView, \
    LactatingEnrolledWomenView, AdolescentGirlsView, AdhaarBeneficiariesView, CleanWaterView, \
    FunctionalToiletView, MedicineKitView, InfantsWeightScaleView, AdultWeightScaleView, AggregationScriptPage, \
    ICDSBugReportView, AWCLocationView, DownloadPDFReport, CheckExportReportStatus, ICDSImagesAccessorAPI, \
    HaveAccessToLocation, InactiveAWW, DownloadExportReport, DishaAPIView, NICIndicatorAPIView, LadySupervisorView, \
    CasDataExport, CasDataExportAPIView, ServiceDeliveryDashboardView, InactiveDashboardUsers

dashboardurls = [
    url(r'^icds_image_accessor/(?P<form_id>[\w\-:]+)/(?P<attachment_id>.*)$',
        ICDSImagesAccessorAPI.as_view(), name='icds_image_accessor'),
    url(r'^data_export', CasDataExportAPIView.as_view(), name='data_export_api'),
    url('^', DashboardView.as_view(), name='icds_dashboard'),
]

maternal_and_child_urls = [
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
]

cas_reach_urls = [
    url(
        r'^awc_daily_status/(?P<step>[\w-]+)/',
        AWCDailyStatusView.as_view(),
        name='awc_daily_status'),
    url(
        r'^awcs_covered/(?P<step>[\w-]+)/',
        AWCsCoveredView.as_view(),
        name='awcs_covered'),
]

demographics_urls = [
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
]

awc_infrastructure_urls = [
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
]

urlpatterns = [
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', TableauView.as_view(), name='icds_tableau'),
    url(r'^icds_dashboard/', include(dashboardurls)),
    url(r'^icds-ng-template/(?P<template>[\w-].+)', IcdsDynamicTemplateView.as_view(), name='icds-ng-template'),
    url(r'^program_summary/(?P<step>[\w-]+)/', ProgramSummaryView.as_view(), name='program_summary'),
    url(r'^lady_supervisor/', LadySupervisorView.as_view(), name='lady_supervisor'),
    url(
        r'^service_delivery_dashboard/',
        ServiceDeliveryDashboardView.as_view(),
        name='service_delivery_dashboard'
    ),
    url(r'^maternal_and_child/', include(maternal_and_child_urls)),
    url(r'^icds_cas_reach/', include(cas_reach_urls)),
    url(r'^demographics/', include(demographics_urls)),
    url(r'^awc_infrastructure/', include(awc_infrastructure_urls)),
    url(r'^awc_reports/(?P<step>[\w-]+)/', AwcReportsView.as_view(), name='awc_reports'),
    url(r'^locations$', LocationView.as_view(), name='icds_locations'),
    url(r'^locations/ancestors$', LocationAncestorsView.as_view(), name='icds_locations_ancestors'),
    url(r'^export_indicator$', ExportIndicatorView.as_view(), name='icds_export_indicator'),
    url(r'^fact_sheets$', FactSheetsView.as_view(), name='fact_sheets'),
    url(r'^aggregation_script/', AggregationScriptPage.as_view(), name=AggregationScriptPage.urlname),
    url(r'^bug_report/', ICDSBugReportView.as_view(), name='icds_bug_report'),
    url(r'^awc_locations/', AWCLocationView.as_view(), name='awc_locations'),
    url(r'^download_pdf/', DownloadPDFReport.as_view(), name='icds_download_pdf'),
    url(r'^download_excel/', DownloadExportReport.as_view(), name='icds_download_excel'),
    url(r'^issnip_pdf_status/', CheckExportReportStatus.as_view(), name='issnip_pdf_status'),
    url(r'^have_access_to_location/', HaveAccessToLocation.as_view(), name='have_access_to_location'),
    url(r'^inactive_aww', InactiveAWW.as_view(), name='inactive_aww'),
    url(r'^inactive_dashboard_users', InactiveDashboardUsers.as_view(), name='inactive_aww'),
    url(r'^health_indicators', DishaAPIView.as_view(), name='disha_api'),
    url(r'^nic_indicators', NICIndicatorAPIView.as_view(), name='nic_indicator_api'),
    url(r'^cas_export', CasDataExport.as_view(), name='cas_export'),
]
