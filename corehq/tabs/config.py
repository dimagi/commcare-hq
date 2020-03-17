from corehq.apps.styleguide.tabs import SGExampleTab, SimpleCrispyFormSGExample
from corehq.tabs.tabclasses import (
    AccountingTab,
    AdminTab,
    ApplicationsTab,
    CloudcareTab,
    DashboardTab,
    EnterpriseSettingsTab,
    HostedCCZTab,
    MessagingTab,
    MySettingsTab,
    ProjectDataTab,
    ProjectReportsTab,
    ProjectSettingsTab,
    ProjectUsersTab,
    SetupTab,
    SMSAdminTab,
    TranslationsTab,
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
    # invisible
    ProjectSettingsTab,
    EnterpriseSettingsTab,
    MySettingsTab,
    TranslationsTab,
    HostedCCZTab,
    # Admin
    AdminTab,
    SMSAdminTab,
    AccountingTab,
    # Styleguide
    SGExampleTab,
    SimpleCrispyFormSGExample,
)
