from corehq.apps.hqwebapp.models import (
    DashboardTab,
    ProjectInfoTab,
    ReportsTab,
    ProjectDataTab,
    SetupTab,
    ProjectUsersTab,
    ApplicationsTab,
    CloudcareTab,
    MessagingTab,
    ExchangeTab,
    OrgReportTab,
    OrgSettingsTab, # separate menu?
    AdminTab
)
from corehq.apps.styleguide.tabs import SGExampleTab

MENU_TABS = (
    DashboardTab,
    ProjectInfoTab,
    ReportsTab,
    ProjectDataTab,
    SetupTab,
    ProjectUsersTab,
    ApplicationsTab,
    CloudcareTab,
    MessagingTab,
    ExchangeTab,
    OrgReportTab,
    OrgSettingsTab, # separate menu?
    AdminTab,
    SGExampleTab,
)
