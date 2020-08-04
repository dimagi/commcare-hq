from corehq.toggles import (
    NAMESPACE_DOMAIN,
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
    relevant_environments={"icds", "icds-staging"}
)

ICDS_DASHBOARD_SHOW_MOBILE_APK = DynamicallyPredictablyRandomToggle(
    'icds_dashboard_show_mobile_apk',
    'Show a "Mobile APK" download link on the ICDS Dashboard',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
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
    relevant_environments={'icds', 'icds-staging'},
)

ICDS_NIC_INDICATOR_API = StaticToggle(
    'icds_nic_indicator_acess',
    'ICDS: Dashboard Indicator API for NIC',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
    relevant_environments={'icds', 'icds-staging'},
)

AP_WEBSERVICE = StaticToggle(
    'ap_webservice',
    'ICDS: ENABLE AP webservice',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
    relevant_environments={'icds', 'icds-staging'},
)

PARALLEL_MPR_ASR_REPORT = StaticToggle(
    'parallel_mpr_asr_report',
    'Release parallel loading of MPR and ASR report',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
)

MANAGE_CCZ_HOSTING = StaticToggle(
    'manage_ccz_hosting',
    'Allow project to manage ccz hosting',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={'icds', 'icds-staging'},
)

MPR_ASR_CONDITIONAL_AGG = DynamicallyPredictablyRandomToggle(
    'mpr_asr_conditional_agg',
    'Improved MPR ASR by doing aggregation at selected level',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
)

PHI_CAS_INTEGRATION = StaticToggle(
    'phi_cas_integration',
    'Integrate with PHI Api to search and validate beneficiaries',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    relevant_environments={"icds", "icds-staging"}
)

DAILY_INDICATORS = StaticToggle(
    'daily_indicators',
    'Enable daily indicators api',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
)

MWCD_INDICATORS = StaticToggle(
    'MWCD_INDICATORS',
    'Enable MWCD indicators API',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
)

ICDS_GOVERNANCE_DASHABOARD_API = StaticToggle(
    'governance_apis',
    'ICDS: Dashboard Governance dashboard API',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
    relevant_environments={'icds', 'icds-staging'},
)

RUN_CUSTOM_DATA_PULL_REQUESTS = StaticToggle(
    'run_custom_data_pull_requests',
    '[ICDS] Initiate custom data pull requests from UI',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
)

RUN_DATA_MANAGEMENT_TASKS = StaticToggle(
    'run_data_management_tasks',
    '[ICDS] Run data management tasks',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    relevant_environments={"icds", "icds-staging"}
)

ICDS_BIHAR_DEMOGRAPHICS_API = StaticToggle(
    'bihar_demographics_api',
    'ICDS: Bihar Demographics API',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
    relevant_environments={'icds', 'icds-staging'},

)

ICDS_LOCATION_REASSIGNMENT_AGG = StaticToggle(
    'location_reassignment_agg',
    'ICDS: Use aggregation modifications for location reassignment',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    relevant_environments={'icds', 'icds-staging'},
)
