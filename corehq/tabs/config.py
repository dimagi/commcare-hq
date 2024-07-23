from corehq.apps.styleguide.examples.bootstrap5.tabs import StyleguideExamplesTab
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
    # Admin
    AdminTab,
    SMSAdminTab,
    AccountingTab,
    # Bootstrap3 Styleguide
    SGExampleTab,
    SimpleCrispyFormSGExample,
    # Bootstrap5 Styleguide
    StyleguideExamplesTab,
)
