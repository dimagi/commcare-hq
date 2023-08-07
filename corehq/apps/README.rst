Django Apps in CommCare HQ
##########################

Most CommCare HQ functionality is contained in a django app.
A few areas are contained in ``corehq`` or ``corehq/ex-submodules``,
so for a full overview, check those READMEs as well.

Primary Apps
^^^^^^^^^^^^
These apps are major parts of the system and most have frequent, active development.

accounting
   Billing functionality: accounts, subscriptions, software plans, etc.
   This includes the UI for internal operations users to modify these objects.
   Accessing this UI requires running the ``add_operations_user`` command.
api
   APIs to read and write CommCare data for a given project space. Most APIs are externally facing. However, there
   are a few that are used internally e.g. for report filters. APIs are built using Tastypie.
app_manager
   UI and tooling for configuring and releasing CommCare applications.
   Form Builder, for configuring forms themselves, is called here but
   is primarily stored in the separate `Vellum <https://github.com/dimagi/Vellum/>`_ repo.
auditcare
    A couch-based set of auditing tools. All page views in CommCare HQ are recorded in auditcare.
    This backs the User Audit Log report, which allows admins to view a given user's historical actions.
    Doing non-user-based queries is prohibitively slow.
celery
   A Django app that initializes the default/current Celery app during Django
   setup.
cloudcare
   Web Apps, a web-based interface for data entry, with essentially the same functionality
   as CommCare Mobile, but available via HQ to both web and mobile users. This app contains the HQ
   parts of this code, which interfaces with `Formplayer <https://github.com/dimagi/formplayer/>`_
   to ultimately run functionality in the `commcare-core <https://github.com/dimagi/commcare-core/>`_
   repo, which is shared with CommCare Mobile.
domain
   Domains, called "project spaces" in user-facing content, are the core sandboxes of CommCare. Almost
   all features and UIs in CommCare are in the context of a domain.
export
   Configurations for exporting project data, typically forms or cases, to an excel download.
hqmedia
   Multimedia handling, primarily used in applications.
hqwebapp
   Core UI code for the HQ site. Includes things like the standard error pages,
   javascript widgets, login views, etc.
locations
   Locations provide a hierarchical way to organize CommCare users and data.
ota
   Contains a number of the API endpoints used by CommCare mobile including sync / restore, case search, case claim, heartbeat and  recovery measures. This is used by both CommCare mobile and formplayer.
reports
   Standard, pre-canned reports to view project data: Submit History, Worker Activity Report, etc.
reports_core
   More reporting code that resulted from an attempt to re-architect the report class structure.
sms
   Features to send SMS and emails via CommCare HQ. Much of the underlying code is in ``corehq.messaging``.
userreports
   User-defined reports. Intertwined with other report-related apps.
users
   Users of CommCare HQ and/or CommCare mobile. The primary class dealing with users is ``CouchUser``,
   a representation of the user in couch. ``CouchUser`` has the subclasses ``WebUser`` and ``CommCareUser``
   to distinguish between admin-type users who primarily use CommCare HQ and data entry users who primarily use
   CommCare Mobile. The distinction between web and mobile users is blurry, especially with the advent of
   Web Apps for data entry in HQ.

Secondary Apps
^^^^^^^^^^^^^^^^^^^^
These apps are maintained and updated regularly, but are a bit less core than the set above.

case_importer
   Bulk import of cases.
custom_data_fields
   This allows users to add arbitrary data to mobile users, locations, and products, which can then
   be referenced in applications.
data_dictionary
   The data dictionary documents a project's data model, specifically, its case types and case properties.
   This makes it possible to reference those definitions throughout the app-building process without needing
   to repeatedly re-parse it out of the application configuration.
   The data dictionary is used partially for project documentation but is also referenced in a few other
   parts of HQ: for example, when configuring case properties to be updated in a form, app manager will
   pull the properties' descriptions from the data dictionary.
data_interfaces
   Functionality for taking a few specific actions on project data, such as reassigning cases in bulk.
   Most of this app relies heavily on standard reporting functionality.
enterprise
    Enterprise related functionality lives here, with a few exceptions in enterprise permissions functionality in users and linked project spaces.
fixtures
   The term "fixtures" comes from the `XML data model <https://github.com/dimagi/commcare-core/wiki/fixtures>`_ used to send custom structured data to the mobile devices (separate from case data). During the sync request with the mobile device, various different fixtures may be sent to the device including lookup tables, locations and mobile reports. This Django app only deals with the "lookup table" fixtures. It provides the UI for creating and editing them and the code to serialize them to XML.
groups
   Users can be assigned to groups for the purposes of sharing cases within a group and for reporting purposes.
hqadmin
   Internal admin functionality used by the development, support, QA, and product teams.
linked_domain
   Functionality to share certain configuration data between domains: apps, lookup tables, report definitions, etc.
   Work is done in a primary "upstream" domain, and then that domain's data models are copied to one or more
   "downstream" domains. This is most often used to set up a development => production workflow, where changes are made
   in the development domain and then pushed to the production domain, where real project data is entered.
   Linked domains are also used by certain enterprise-type projects that manage one program across multiple regions
   and use a separate downstream domain for each region.
registration
   Workflows for creating new accounts on HQ.
reminders
   A subset of SMS/messaging, including functionality around incoming SMS keywords. "Reminders" is a leftover term from a previous iteration of the messaging framework.
saved_reports
   Functionality to let users save a specific set of report filters and optionally run reports with those filters on a scheduled basis.
toggle_ui
   Framework for feature flags, which are used to limit internal features to specific domains and/or users.
translations
   Functionality for managing application translations, including integration with Transifex, which is used by a small number of projects.
user_importer
   Bulk importing of users.

Tertiary Apps
^^^^^^^^^^^^^
These apps may be useful parts of the system but don't have as much active development as the groups above.

aggregate_ucrs
   An experimental framework for creating more complex reporting pipelines based off the UCR framework.
analytics
   Integrations with third-party analytics tools such as Google Analytics and Kissmetrics.
   Also contains internal product-focused tools such as AB testing functionality.
builds
   Models relating to CommCare Mobile builds, so that app builders can control which mobile version their apps use.
case_search
   Models and utils related to searching for cases using Elasticsearch. Used for Case Claim and the Case List Explorer. 
dashboard
   The tiled UI that acts as the main landing page for HQ.
formplayer_api
   Functionality interacting with formplayer, primarily used by SMS surveys.
mobile_auth
   Generates the XML needed to authorize mobile users.
notifications
   "Banner" notifications used by the support team to notify users of upcoming downtime,
   ongoing issues, etc.
receiverwrapper
   Contains the API for receiving XML form submissions. This app mostly deals with the interfacing portion of the
   API including auth, rate limiting etc. but not the actual data processing which is contained in the
   `form_processor` app.
settings
   API keys and 2FA functionality.
smsbillables
   Billing functionality relating to charging for SMS, allowing us to pass carrier charges on to clients.
smsforms
   SMS surveys allow end users to interact with a CommCare form via SMS instead of
   via mobile or Web Apps. This is part of ``messaging``.
sso
   Features related to Single Sign On.
styleguide
   Documentation of best practices for UI development, including live examples of common patterns.
zapier
   Integration with `Zapier <https://zapier.com/>`_

Engineering Apps
^^^^^^^^^^^^^^^^
These apps are developer-facing tools.

cachehq
   Caching functinality for CouchDB.
change_feed
   Infrastructure for propagating changes in primary data stores (couch, postgres) to secondary sources (ElasticSearch).
cleanup
   Miscellaneous commands for cleaning up data: deleting duplicate mobile users, deleting couch documents for models that have been moved to postgres, etc.
data_analytics
   Internal impact-related metrics.
data_pipeline_audit
   Tools used to audit the async data pipeline (change feeds / pillows) to validate the integrity of secondary
   sources (mostly Elasticsearch). These tools are not used routinely.
domain_migration_flags
   Dynamic flags that are used to indicate when a data migration is taking place for a specific domain. The flags are
   checked in various places throughout the code and will restrict access to certain features when enabled. These flags
   are set during large data migrations such as moving case & form data from Couch -> SQL, migrating a domain to a
   different CommCare instance.
dump_reload
   Tools used to dump a domain's data to disk and reload it from disk. This is used to move a domain from one CommCare instance to another e.g. from a managed environment to self hosted environment.
es
   Internal APIs for creating and running ElasticSearch queries.
hqcase
   Utility functions for handling cases, such as the ability to programmatically submit cases.
mocha
   JavaScript testing framework.

Limited-Use and Retired Apps
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
These apps are limited to a small set of clients or on a deprecation path.

appstore
   The CommCare Exchange, a deprecated feature that allowed projects to publish their projects in a self-service manner
   and download other organizations' projects. This process is now supported internally by the support team. The UI
   portions of this app have been removed, but the data models are still necessary for the internal processes.
callcenter
   The call center application setting allows an application to reference a mobile user as a case that can be monitored using CommCare.  This allows supervisors to view their workforce within CommCare.
casegroups
   Functionality around grouping cases in large projects and then taking action on those groups.
commtrack
   CommCare Supply, a large and advanced set of functionality for using CommCare in logistics management.
consumption
   Part of CommCare Supply.
dropbox
   Functionality to allow users to download large HQ files to dropbox instead of their local machines. This is likely being deprecated.
integration
   Various integrations with biometrics devices, third-party APIs, etc.
ivr
   Functionality to allow users to fill out forms using interactive voice response. Largely deprecated.
products
   Part of CommCare Supply.
programs
   Part of CommCare Supply.
