from corehq.apps.styleguide.tabs import SGExampleTab, SimpleCrispyFormSGExample
from corehq.tabs.tabclasses import (
    AccountingTab,
    AdminTab,
    ApplicationsTab,
    CloudcareTab,
    DashboardTab,
    EnterpriseSettingsTab,
    MessagingTab,
    MySettingsTab,
    ProjectDataTab,
    ProjectReportsTab,
    ProjectSettingsTab,
    ProjectUsersTab,
    SetupTab,
    SMSAdminTab,
    TranslationsTab,
    AttendanceTrackingTab,
    GeospatialTab,
)

MENU_TABS = (
    DashboardTab,
    ProjectReportsTab,
    ProjectDataTab,
    SetupTab,
    ProjectUsersTab,
    ApplicationsTab,
    CloudcareTab,
    MessagingTab,
    AttendanceTrackingTab,
    # invisible
    ProjectSettingsTab,
    EnterpriseSettingsTab,
    MySettingsTab,
    TranslationsTab,
    GeospatialTab,
    # Admin
    AdminTab,
    SMSAdminTab,
    AccountingTab,
    # Styleguide
    SGExampleTab,
    SimpleCrispyFormSGExample,
)
