from corehq.apps.styleguide.tabs import SGExampleTab, SimpleCrispyFormSGExample
from corehq.tabs.tabclasses import DashboardTab, ProjectReportsTab, SetupTab, \
    ProjectDataTab, ApplicationsTab, CloudcareTab, MessagingTab, ProjectUsersTab, \
    AdminTab, SMSAdminTab, AccountingTab, ProjectSettingsTab, \
    MySettingsTab, EnterpriseSettingsTab, TranslationsTab, HostedCCZTab

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
