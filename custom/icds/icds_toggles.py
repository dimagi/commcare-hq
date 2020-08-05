from corehq.toggles import (
    NAMESPACE_DOMAIN,
    NAMESPACE_OTHER,
    NAMESPACE_USER,
    TAG_CUSTOM,
    DynamicallyPredictablyRandomToggle,
    StaticToggle,
)

DASHBOARD_ICDS_REPORT = StaticToggle(
    'dashboard_icds_reports',
    'ICDS: Enable access to the dashboard reports for ICDS',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

ICDS_DASHBOARD_SHOW_MOBILE_APK = DynamicallyPredictablyRandomToggle(
    'icds_dashboard_show_mobile_apk',
    'Show a "Mobile APK" download link on the ICDS Dashboard',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

ICDS_DASHBOARD_TEMPORARY_DOWNTIME = StaticToggle(
    'icds_dashboard_temporary_downtime',
    'ICDS: Temporarily disable the ICDS dashboard by showing a downtime page. '
    'This can be cicurmvented by adding "?bypass-downtime=True" to the end of the url.',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

ICDS_DISHA_API = StaticToggle(
    'icds_disha_access',
    'ICDS: Access DISHA API',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
)

ICDS_NIC_INDICATOR_API = StaticToggle(
    'icds_nic_indicator_acess',
    'ICDS: Dashboard Indicator API for NIC',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
)

AP_WEBSERVICE = StaticToggle(
    'ap_webservice',
    'ICDS: ENABLE AP webservice',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
)

PARALLEL_MPR_ASR_REPORT = StaticToggle(
    'parallel_mpr_asr_report',
    'Release parallel loading of MPR and ASR report',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

MANAGE_CCZ_HOSTING = StaticToggle(
    'manage_ccz_hosting',
    'Allow project to manage ccz hosting',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

MPR_ASR_CONDITIONAL_AGG = DynamicallyPredictablyRandomToggle(
    'mpr_asr_conditional_agg',
    'Improved MPR ASR by doing aggregation at selected level',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

PHI_CAS_INTEGRATION = StaticToggle(
    'phi_cas_integration',
    'Integrate with PHI Api to search and validate beneficiaries',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

DAILY_INDICATORS = StaticToggle(
    'daily_indicators',
    'Enable daily indicators api',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

MWCD_INDICATORS = StaticToggle(
    'MWCD_INDICATORS',
    'Enable MWCD indicators API',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

ICDS_GOVERNANCE_DASHABOARD_API = StaticToggle(
    'governance_apis',
    'ICDS: Dashboard Governance dashboard API',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
)

RUN_CUSTOM_DATA_PULL_REQUESTS = StaticToggle(
    'run_custom_data_pull_requests',
    '[ICDS] Initiate custom data pull requests from UI',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

RUN_DATA_MANAGEMENT_TASKS = StaticToggle(
    'run_data_management_tasks',
    '[ICDS] Run data management tasks',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

ICDS_BIHAR_DEMOGRAPHICS_API = StaticToggle(
    'bihar_demographics_api',
    'ICDS: Bihar Demographics API',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
)

ICDS_LOCATION_REASSIGNMENT_AGG = StaticToggle(
    'location_reassignment_agg',
    'ICDS: Use aggregation modifications for location reassignment',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

ENABLE_ICDS_DASHBOARD_RELEASE_NOTES_UPDATE = StaticToggle(
    'enable_icds_dashboard_release_notes_update',
    'Enable updating ICDS dashboard release notes for specific users',
    TAG_CUSTOM,
    [NAMESPACE_USER]
)

ICDS_UCR_ELASTICSEARCH_DOC_LOADING = DynamicallyPredictablyRandomToggle(
    'icds_ucr_elasticsearch_doc_loading',
    'ICDS: Load related form docs from ElasticSearch instead of Riak',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_OTHER],
)
