from corehq.apps.styleguide.tabs import SGExampleTab, SimpleCrispyFormSGExample, \
    ControlsDemoSGExample
from corehq.tabs.tabclasses import DashboardTab, ProjectReportsTab, ProjectInfoTab, SetupTab, \
    ProjectDataTab, ApplicationsTab, CloudcareTab, MessagingTab, ProjectUsersTab, \
    AdminTab, IndicatorAdminTab

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
    AdminTab,
    # Styleguide
    SGExampleTab,
    SimpleCrispyFormSGExample,
    ControlsDemoSGExample,
)
