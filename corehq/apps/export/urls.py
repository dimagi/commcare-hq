from django.conf.urls import re_path as url

from corehq.apps.export.views.download import (
    BulkDownloadNewFormExportView,
    DownloadDETSchemaView,
    DownloadNewCaseExportView,
    DownloadNewFormExportView,
    DownloadNewSmsExportView,
    add_export_email_request,
    has_multimedia,
    poll_custom_export_download,
    prepare_custom_export,
    prepare_form_multimedia,
)
from corehq.apps.export.views.edit import (
    EditCaseDailySavedExportView,
    EditCaseFeedView,
    EditExportDescription,
    EditExportNameView,
    EditFormDailySavedExportView,
    EditFormFeedView,
    EditNewCustomCaseExportView,
    EditNewCustomFormExportView,
    EditODataCaseFeedView,
    EditODataFormFeedView,
)
from corehq.apps.export.views.incremental import (
    IncrementalExportView,
    incremental_export_checkpoint_file,
    incremental_export_reset_checkpoint,
    incremental_export_resend_all,
)
from corehq.apps.export.views.list import (
    CaseExportListView,
    DailySavedExportListView,
    DashboardFeedListView,
    DeIdDailySavedExportListView,
    DeIdDashboardFeedListView,
    DeIdFormExportListView,
    FormExportListView,
    ODataFeedListView,
    LiveGoogleSheetListView,
    commit_filters,
    download_daily_saved_export,
    get_app_data_drilldown_values,
    get_exports_page,
    get_saved_export_progress,
    submit_app_data_drilldown_form,
    toggle_saved_export_enabled,
    update_emailed_export_data,
)
from corehq.apps.export.views.new import (
    CopyExportView,
    CreateNewCaseFeedView,
    CreateNewCustomCaseExportView,
    CreateNewCustomFormExportView,
    CreateNewDailySavedCaseExport,
    CreateNewDailySavedFormExport,
    CreateNewFormFeedView,
    CreateODataCaseFeedView,
    CreateODataFormFeedView,
    CreateGoogleSheetCaseView,
    CreateGoogleSheetFormView,
    DeleteNewCustomExportView,
)
from corehq.apps.export.views.utils import (
    DailySavedExportPaywall,
    DashboardFeedPaywall,
    DataFileDownloadDetail,
    DataFileDownloadList,
    GenerateSchemaFromAllBuildsView,
)
from corehq.apps.hqwebapp.decorators import waf_allow

urlpatterns = [
    # Export list views
    url(r"^custom/form/$",
        FormExportListView.as_view(),
        name=FormExportListView.urlname),
    url(r"^custom/form_deid/$",
        DeIdFormExportListView.as_view(),
        name=DeIdFormExportListView.urlname),
    url(r"^custom/daily_saved_deid/$",
        DeIdDailySavedExportListView.as_view(),
        name=DeIdDailySavedExportListView.urlname),
    url(r"^custom/feed_deid/$",
        DeIdDashboardFeedListView.as_view(),
        name=DeIdDashboardFeedListView.urlname),
    url(r"^custom/case/$",
        CaseExportListView.as_view(),
        name=CaseExportListView.urlname),
    url(r"^custom/daily_saved/$",
        DailySavedExportListView.as_view(),
        name=DailySavedExportListView.urlname),
    url(r"^custom/dashboard_feed/$",
        DashboardFeedListView.as_view(),
        name=DashboardFeedListView.urlname),
    url(r"^custom/odata_feed/$",
        ODataFeedListView.as_view(),
        name=ODataFeedListView.urlname),
    url(r"^custom/google_sheet/$",
        LiveGoogleSheetListView.as_view(),
        name=LiveGoogleSheetListView.urlname),
    url(r"^custom/download_data_files/$",
        waf_allow('XSS_BODY')(DataFileDownloadList.as_view()),
        name=DataFileDownloadList.urlname),
    url(r"^custom/download_data_files/(?P<pk>[\w\-]+)/(?P<filename>.*)$",
        DataFileDownloadDetail.as_view(),
        name=DataFileDownloadDetail.urlname),
    url(r"^custom/inc_export/$",
        IncrementalExportView.as_view(),
        name=IncrementalExportView.urlname),
    url(r"^custom/inc_export_file/(?P<checkpoint_id>[\w\-]+)$",
        incremental_export_checkpoint_file,
        name='incremental_export_checkpoint_file'),
    url(r"^custom/inc_export_reset/(?P<checkpoint_id>[\w\-]+)$",
        incremental_export_reset_checkpoint,
        name='incremental_export_reset_checkpoint'),
    url(r"^custom/inc_export_resend_all/(?P<incremental_export_id>[\w\-]+)$",
        incremental_export_resend_all,
        name='incremental_export_resend_all'),

    # New export configuration views
    url(r"^custom/new/form/create$",
        CreateNewCustomFormExportView.as_view(),
        name=CreateNewCustomFormExportView.urlname),
    url(r"^custom/new/form_feed/create$",
        CreateNewFormFeedView.as_view(),
        name=CreateNewFormFeedView.urlname),
    url(r"^custom/new/form_daily_saved/create$",
        CreateNewDailySavedFormExport.as_view(),
        name=CreateNewDailySavedFormExport.urlname),
    url(r"^custom/new/case/create$",
        CreateNewCustomCaseExportView.as_view(),
        name=CreateNewCustomCaseExportView.urlname),
    url(r"^custom/new/case_feed/create$",
        CreateNewCaseFeedView.as_view(),
        name=CreateNewCaseFeedView.urlname),
    url(r"^custom/new/odata_case_feed/create$",
        CreateODataCaseFeedView.as_view(),
        name=CreateODataCaseFeedView.urlname),
    url(r"^custom/new/odata_form_feed/create$",
        CreateODataFormFeedView.as_view(),
        name=CreateODataFormFeedView.urlname),
    url(r"^custom/new/live_google_sheet_case/create$",
        CreateGoogleSheetCaseView.as_view(),
        name=CreateGoogleSheetCaseView.urlname),
    url(r"^custom/new/live_google_sheet_form/create$",
        CreateGoogleSheetFormView.as_view(),
        name=CreateGoogleSheetFormView.urlname),
    url(r"^custom/new/case_daily_saved/create$",
        CreateNewDailySavedCaseExport.as_view(),
        name=CreateNewDailySavedCaseExport.urlname),

    # Data Download views
    url(r"^custom/new/form/download/bulk/$",
        BulkDownloadNewFormExportView.as_view(),
        name=BulkDownloadNewFormExportView.urlname),
    url(r"^custom/new/form/download/(?P<export_id>[\w\-]+)/$",
        DownloadNewFormExportView.as_view(),
        name=DownloadNewFormExportView.urlname),
    url(r"^custom/new/case/download/(?P<export_id>[\w\-]+)/$",
        DownloadNewCaseExportView.as_view(),
        name=DownloadNewCaseExportView.urlname),
    url(r"^custom/dailysaved/download/(?P<export_instance_id>[\w\-]+)/$",
        download_daily_saved_export,
        name="download_daily_saved_export"),
    url(r"^custom/new/sms/download/$",
        DownloadNewSmsExportView.as_view(),
        name=DownloadNewSmsExportView.urlname),

    # Schema Download views
    url(r"^custom/schema/det/download/(?P<export_instance_id>[\w\-]+)/$",
        DownloadDETSchemaView.as_view(),
        name=DownloadDETSchemaView.urlname),

    # Edit export views
    url(r"^custom/new/form/edit/(?P<export_id>[\w\-]+)/$",
        EditNewCustomFormExportView.as_view(),
        name=EditNewCustomFormExportView.urlname),
    url(r"^custom/form_feed/edit/(?P<export_id>[\w\-]+)/$",
        EditFormFeedView.as_view(),
        name=EditFormFeedView.urlname),
    url(r"^custom/form_daily_saved/edit/(?P<export_id>[\w\-]+)/$",
        EditFormDailySavedExportView.as_view(),
        name=EditFormDailySavedExportView.urlname),
    url(r"^custom/new/case/edit/(?P<export_id>[\w\-]+)/$",
        EditNewCustomCaseExportView.as_view(),
        name=EditNewCustomCaseExportView.urlname),
    url(r"^custom/odata_case_feed/edit/(?P<export_id>[\w\-]+)/$",
        EditODataCaseFeedView.as_view(),
        name=EditODataCaseFeedView.urlname),
    url(r"^custom/odata_form_feed/edit/(?P<export_id>[\w\-]+)/$",
        EditODataFormFeedView.as_view(),
        name=EditODataFormFeedView.urlname),
    url(r"^custom/case_feed/edit/(?P<export_id>[\w\-]+)/$",
        EditCaseFeedView.as_view(),
        name=EditCaseFeedView.urlname),
    url(r"^custom/case_daily_saved/edit/(?P<export_id>[\w\-]+)/$",
        EditCaseDailySavedExportView.as_view(),
        name=EditCaseDailySavedExportView.urlname),
    url(r"^custom/copy/(?P<export_id>[\w\-]+)/$",
        CopyExportView.as_view(),
        name=CopyExportView.urlname),
    url(r'^custom/edit_export_name/(?P<export_id>[\w\-]+)/$',
        EditExportNameView.as_view(),
        name=EditExportNameView.urlname),
    url(r'^custom/edit_export_description/(?P<export_id>[\w\-]+)/$',
        EditExportDescription.as_view(),
        name=EditExportDescription.urlname),
    url(r'^add_export_email_request/$', add_export_email_request, name='add_export_email_request'),
    url(r'^commit_filters/$', commit_filters, name='commit_filters'),
    url(r'^get_app_data_drilldown_values/$', get_app_data_drilldown_values, name='get_app_data_drilldown_values'),
    url(r'^get_exports_page/$', get_exports_page, name='get_exports_page'),
    url(r'^get_saved_export_progress/$', get_saved_export_progress, name='get_saved_export_progress'),
    url(r'^has_multimedia/$', has_multimedia, name='has_multimedia'),
    url(r'^poll_custom_export_download/$', poll_custom_export_download, name='poll_custom_export_download'),
    url(r'^prepare_custom_export/$', prepare_custom_export, name='prepare_custom_export'),
    url(r'^prepare_form_multimedia/$', prepare_form_multimedia, name='prepare_form_multimedia'),
    url(r'^submit_app_data_drilldown_form/$', submit_app_data_drilldown_form,
        name='submit_app_data_drilldown_form'),
    url(r'^toggle_saved_export_enabled/$', toggle_saved_export_enabled, name='toggle_saved_export_enabled'),
    url(r'^update_emailed_export_data/$', update_emailed_export_data, name='update_emailed_export_data'),

    # Delete export views
    url(r"^custom/new/(?P<export_type>[\w\-]+)/delete/(?P<export_id>[\w\-]+)/$",
        DeleteNewCustomExportView.as_view(),
        name=DeleteNewCustomExportView.urlname),

    # Paywalls
    url(r"^dashboard_feed/paywall/$",
        DashboardFeedPaywall.as_view(),
        name=DashboardFeedPaywall.urlname),
    url(r"^daily_saved/paywall/$",
        DailySavedExportPaywall.as_view(),
        name=DailySavedExportPaywall.urlname),

    url(r"^build_full_schema/$",
        GenerateSchemaFromAllBuildsView.as_view(),
        name=GenerateSchemaFromAllBuildsView.urlname),
]
