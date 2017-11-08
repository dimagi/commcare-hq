from __future__ import absolute_import
from corehq.apps.styleguide.tabs import SGExampleTab, SimpleCrispyFormSGExample, \
    ControlsDemoSGExample
from corehq.tabs.tabclasses import DashboardTab, ProjectReportsTab, ProjectInfoTab, SetupTab, \
    ProjectDataTab, ApplicationsTab, CloudcareTab, MessagingTab, ProjectUsersTab, \
    AdminTab, IndicatorAdminTab, SMSAdminTab, AccountingTab, ProjectSettingsTab, \
    MySettingsTab

MENU_TABS = (
    DashboardTab,
    ProjectInfoTab,
    ProjectReportsTab,
    IndicatorAdminTab,
    ProjectDataTab,
    SetupTab,
    ProjectUsersTab,
    ApplicationsTab,
    CloudcareTab,
    MessagingTab,
    # invisible
    ProjectSettingsTab,
    MySettingsTab,
    # Admin
    AdminTab,
    SMSAdminTab,
    AccountingTab,
    # Styleguide
    SGExampleTab,
    SimpleCrispyFormSGExample,
    ControlsDemoSGExample,
)
