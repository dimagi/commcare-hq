import _ from "underscore";
import "commcarehq";
import "hqwebapp/js/htmx_base";
import initialPageData from "hqwebapp/js/initial_page_data";
import toggles from "hqwebapp/js/toggles";
import privileges from "hqwebapp/js/privileges";
import Alpine from "alpinejs";

const removeItem = (array, item) => {
    const index = array.indexOf(item);
    if (index > -1) {
        array.splice(index, 1);
    }
};

const [NONE, ALL, SELECTED] = ["none", "all", "selected"];

const selectPermissionModel = (args) => {
    const {
        text,
        listHeading,
        showAlreadyConfiguredWarning = false,
        permissionObj,
        accessKey,
        listKey,
        listChoices,
    } = args;

    const handler = {
        id: accessKey,
        text: text,
        listHeading: listHeading,
        showAlreadyConfiguredWarning: showAlreadyConfiguredWarning,
        state: NONE,
        specificCache: [],

        get selection() {
            return this.state;
        },

        set selection(value) {
            this.state = value;
            if (value === ALL) {
                permissionObj[accessKey] = true;
                permissionObj[listKey] = [];
            } else if (value === NONE) {
                permissionObj[accessKey] = false;
                permissionObj[listKey] = [];
            } else {
                permissionObj[accessKey] = false;
                permissionObj[listKey] = [...this.specificCache];
            }
        },

        get showItems() {
            return this.selection === SELECTED;
        },

        get hasError() {
            const list = permissionObj[listKey];
            return list !== undefined && list.length === 0;
        },

        init() {
            if (permissionObj[accessKey]) {
                this.state = ALL;
            } else if (!permissionObj[listKey] || permissionObj[listKey].length === 0) {
                this.state = NONE;
            } else {
                this.state = SELECTED;
                this.specificCache = [...permissionObj[listKey]];
            }
        }
    };

    handler.specific = _.map(listChoices, (item) => ({
        slug: item._id || item.slug,
        name: item.name,
        get value() {
            const list = permissionObj[listKey] || [];
            return list.indexOf(this.slug) !== -1;
        },
        set value(checked) {
            if (checked) {
                permissionObj[listKey].push(this.slug);
                handler.specificCache.push(this.slug);
            } else {
                removeItem(permissionObj[listKey], this.slug);
                removeItem(handler.specificCache, this.slug);
            }
        }
    }));

    return handler;
};

Alpine.data('initRole', (roleJson) => {

    console.log(`initRole: ${JSON.stringify(roleJson, null, 2)}`);

    return {
        role: roleJson,
        isSaving: false,
        roleError: '',
        allowEdit: initialPageData.get("can_edit_roles"),
        accessAreas: [],
        erm: {},
        reports: [],
        init() {
            const self = this;
            this.accessAreas = [
                {
                    showOption: true,
                    get editPermission() {
                        return self.role.permissions.edit_web_users;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_web_users = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_web_users;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_web_users = value;
                    },
                    text: gettext("<strong>Web Users</strong> &mdash; invite new web users, manage account settings, remove membership"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-web-users-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-web-users-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Mobile Workers"),
                    screenReaderViewOnlyText: gettext("View-Only Mobile Workers"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return toggles.toggleEnabled("TABLEAU_USER_SYNCING") &&
                            (self.role.permissions.edit_web_users || self.role.permissions.view_web_users);
                    },
                    get editPermission() {
                        return self.role.permissions.edit_user_tableau_config;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_user_tableau_config = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_user_tableau_config;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_user_tableau_config = value;
                    },
                    text: gettext("<strong>Manage Tableau Configuration</strong> &mdash; manage tableau configuration for web users"),
                    get showEditCheckbox() {
                        return self.role.permissions.edit_web_users;
                    },
                    editCheckboxLabel: "edit-user-tableau-config-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-user-tableau-config-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View tableau configuration for web users"),
                    screenReaderViewOnlyText: gettext("View-Only tableau configuration for web users"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    showOption: true,
                    get editPermission() {
                        return self.role.permissions.edit_commcare_users;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_commcare_users = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_commcare_users;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_commcare_users = value;
                    },
                    text: gettext("<strong>Mobile Workers</strong> &mdash; create new accounts, manage account settings, deactivate or delete mobile workers."),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-commcare-users-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-commcare-users-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Web Users"),
                    screenReaderViewOnlyText: gettext("View-Only Web Users"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return self.role.permissions.access_all_locations
                    },
                    get editPermission() {
                        return self.role.permissions.edit_groups;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_groups = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_groups;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_groups = value;
                    },
                    text: gettext("<strong>Groups</strong> &mdash; manage groups of mobile workers"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-groups-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-groups-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Groups"),
                    screenReaderViewOnlyText: gettext("View-Only Web Groups"),
                    showAllowCheckbox: true,
                    allowCheckboxText: gettext("Allow changing group membership (requires edit groups)."),
                    allowCheckboxId: "edit-users-groups-checkbox",
                    get allowCheckboxPermission() {
                        return self.role.permissions.edit_users_in_groups
                    },
                    set allowCheckboxPermission(value) { // Add this setter
                        self.role.permissions.edit_users_in_groups = value;
                    },
                },
                {
                    showOption: true,
                    get editPermission() {
                        return self.role.permissions.edit_locations;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_locations = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_locations;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_locations = value;
                    },
                    text: gettext("<strong>Locations</strong> &mdash; manage locations in the Organization's Hierarchy"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-locations-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-locations-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Locations"),
                    screenReaderViewOnlyText: gettext("View-Only Web Locations"),
                    showAllowCheckbox: true,
                    allowCheckboxText: gettext("Allow changing workers at a location."),
                    allowCheckboxId: "edit-users-locations-checkbox",
                    get allowCheckboxPermission() {
                        return self.role.permissions.edit_users_in_locations
                    },
                    set allowCheckboxPermission(value) { // Add this setter
                        self.role.permissions.edit_users_in_locations = value;
                    },
                },
                {
                    get showOption() {
                        return privileges.hasPrivilege('data_dictionary');
                    },
                    get editPermission() {
                        return self.role.permissions.edit_data_dict;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_data_dict = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_data_dict;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_data_dict = value;
                    },
                    text: gettext("<strong>Data Dictionary</strong> &mdash; manage case properties within CommCare HQ"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-data-dict-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-data-dict-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Data Dictionary"),
                    screenReaderViewOnlyText: gettext("View-Only Data Dictionary"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    showOption: true,
                    get editPermission() {
                        return self.role.permissions.edit_data;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_data = value;
                    },
                    viewPermission: null,
                    text: gettext("<strong>Data</strong> &mdash; view, export, and edit form and case data, reassign cases"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-data-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-data-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Data"),
                    screenReaderViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    showOption: true,
                    get editPermission() {
                        return self.role.permissions.edit_messaging;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_messaging = value;
                    },
                    viewPermission: null,
                    text: gettext("<strong>Messaging</strong> &mdash; configure and send conditional alerts"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-messaging-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-messaging-checkbox",
                    screenReaderEditAndViewText: gettext("Access Messaging"),
                    screenReaderViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    // Since disabling "Full Organization Access" automatically disables "Access APIs"
                    // and we never want "Access APIs" without "Full Organization Access",
                    // we hide "Access APIs" when "Full Organization Access" is disabled.
                    // If "Access APIs" is checked though, even if "Full Organization Access" isn't
                    // we always want to show it.
                    // One can no longer make this combination happen in the UI,
                    // but for the small number of existing roles that have this combination
                    // we want it to be displayed.
                    // Unchecking "Access APIs" in this situation will then make the option disappear.
                    get showOption() {
                        return self.role.permissions.access_all_locations || self.role.permissions.access_api;
                    },
                    get editPermission() {
                        return self.role.permissions.access_api;
                    },
                    set editPermission(value) {
                        self.role.permissions.access_api = value;
                    },
                    viewPermission: null,
                    text: gettext("<strong>Access APIs</strong> &mdash; use CommCare HQ APIs to read and update data. Specific APIs may require additional permissions."),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-apis-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-apis-checkbox",
                    screenReaderEditAndViewText: gettext("Access APIs"),
                    screenReaderViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return self.role.permissions.access_all_locations;
                    },
                    get editPermission() {
                        return self.role.permissions.edit_apps;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_apps = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_apps;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_apps = value;
                    },
                    text: gettext("<strong>Applications</strong> &mdash; modify or view the structure and configuration of all applications."),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-apps-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-apps-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View Apps"),
                    screenReaderViewOnlyText: gettext("View-Only Applications"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return self.role.permissions.access_all_locations;
                    },
                    editPermission: false,
                    get viewPermission() {
                        return self.role.permissions.view_roles;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_roles = value;
                    },
                    text: gettext("<strong>Roles &amp; Permissions</strong> &mdash; view web user and mobile worker roles &amp; permissions (only Admins can edit roles)"),
                    showEditCheckbox: false,
                    editCheckboxLabel: "edit-roles-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-roles-checkbox",
                    screenReaderEditAndViewText: null,
                    screenReaderViewOnlyText: gettext("View Roles and Permissions"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return initialPageData.get("data_file_download_enabled");
                    },
                    get editPermission() {
                        return self.role.permissions.edit_file_dropzone;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_file_dropzone = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_file_dropzone;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_file_dropzone = value;
                    },
                    text: gettext("<strong>Dropzone</strong> &mdash; Upload and download files from the file Dropzone"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-dropzone-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-dropzone-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & Download files from the Dropzone "),
                    screenReaderViewOnlyText: gettext("View-Only Dropzone"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return initialPageData.get("export_ownership_enabled");
                    },
                    get editPermission() {
                        return self.role.permissions.edit_shared_exports;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_shared_exports = value;
                    },
                    viewPermission: null,
                    text: gettext("<strong>Manage Shared Exports</strong> &mdash; access and edit the content and structure of shared exports"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-shared-exports-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-shared-exports-checkbox",
                    screenReaderEditAndViewText: null,
                    screenReaderViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return initialPageData.get("attendance_tracking_privilege");
                    },
                    get editPermission() {
                        return self.role.permissions.manage_attendance_tracking;
                    },
                    set editPermission(value) {
                        self.role.permissions.manage_attendance_tracking = value;
                    },
                    viewPermission: null,
                    text: gettext("<strong>Attendance Tracking</strong> &mdash; Coordinate attendance tracking events and users"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-attenance-tracking-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-attenance-tracking-checkbox",
                    screenReaderEditAndViewText: gettext("Edit Attendance Tracking Events"),
                    screenReaderViewOnlyText: gettext("Edit Attendance Tracking Events"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    get showOption() {
                        return toggles.toggleEnabled("SUPERSET_ANALYTICS");
                    },
                    get editPermission() {
                        return self.role.permissions.edit_commcare_analytics;
                    },
                    set editPermission(value) {
                        self.role.permissions.edit_commcare_analytics = value;
                    },
                    get viewPermission() {
                        return self.role.permissions.view_commcare_analytics;
                    },
                    set viewPermission(value) {
                        self.role.permissions.view_commcare_analytics = value;
                    },
                    text: gettext("<strong>CommCare Analytics</strong> &mdash; manage CommCare Analytics associated with this project"),
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-commcare-analytics-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-commcare-analytics-checkbox",
                    screenReaderEditAndViewText: gettext("Edit & View CommCare Analytics"),
                    screenReaderViewOnlyText: gettext("View-Only CommCare Analytics"),
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
            ]; // end accessAreas

            const linkedTitle = privileges.hasPrivilege('release_management') ?
                gettext("Enterprise Release Management") : gettext("Multi-Environment Release Management");

            this.erm = {
                title: linkedTitle,
                get visible() {
                    return privileges.hasPrivilege('release_management') ||
                        privileges.hasPrivilege('lite_release_management');
                },
                access_release_management: {
                    text: gettext('Linked Project Spaces'),
                    checkboxLabel: "erm-checkbox",
                    get checkboxPermission() {
                        return self.role.permissions.access_release_management
                    },
                    set checkboxPermission(value) {
                        self.role.permissions.access_release_management = value;
                    },
                    checkboxText: gettext("Allow role to configure linked project spaces"),
                },
                edit_linked_configs: {
                    text: gettext("Linked Configurations"),
                    checkboxLabel: "erm-edit-linked-checkbox",
                    get checkboxPermission() {
                        return self.role.permissions.edit_linked_configurations
                    },
                    set checkboxPermission(value) {
                        self.role.permissions.edit_linked_configurations = value;
                    },
                    checkboxText: gettext("Allow role to edit linked configurations on this project space"),
                },
            };

            this.reportPermissions = {
                get all() {
                    return self.role.permissions.view_reports;
                },
                set all(value) {
                    self.role.permissions.view_reports = value;
                },
                specific: _.map(initialPageData.get("report_list"), (report) => ({
                    path: report.path,
                    slug: report.slug,
                    name: report.name,
                    get value() {
                        return self.role.permissions.view_report_list.indexOf(report.path) !== -1
                    },
                    set value(value) {
                        if (value) {
                            self.role.permissions.view_report_list.push(report.path);
                        } else {
                            const index = self.role.permissions.view_report_list.indexOf(report.path);
                            if (index > -1) {
                                self.role.permissions.view_report_list.splice(index, 1);
                            }
                        }
                    }
                })),
            };

            this.tableauPermissions = {
                get all() {
                    return self.role.permissions.view_tableau;
                },
                set all(value) {
                    self.role.permissions.view_tableau = value;
                },
                specific: _.map(initialPageData.get("tableau_list"), (report) => ({
                    path: report.path,
                    slug: report.slug,
                    name: report.name,
                    get value() {
                        return self.role.permissions.view_tableau_list.indexOf(report.path) !== -1
                    },
                    set value(value) {
                        if (value) {
                            self.role.permissions.view_tableau_list.push(report.path);
                        } else {
                            const index = self.role.permissions.view_tableau_list.indexOf(report.path);
                            if (index > -1) {
                                self.role.permissions.view_tableau_list.splice(index, 1);
                            }
                        }
                    }
                })),
            };

            this.reports = [
                {
                    get visibilityRestraint() {
                        return self.role.permissions.access_all_locations;
                    },
                    text: gettext("Create and Edit Reports"),
                    checkboxLabel: "create-and-edit-reports-checkbox",
                    get checkboxPermission() {
                        return self.role.permissions.edit_reports;
                    },
                    set checkboxPermission(value) {
                        self.role.permissions.edit_reports = value;
                    },
                    checkboxText: gettext("Allow role to create and edit reports in report builder."),
                },
            ]
            if (toggles.toggleEnabled('USER_CONFIGURABLE_REPORTS')) {
                if (toggles.toggleEnabled('UCR_UPDATED_NAMING')) {
                    this.reports.push({
                        get visibilityRestraint() {
                            return self.role.permissions.access_all_locations;
                        },
                        text: gettext("Create and Edit Custom Web Reports"),
                        checkboxLabel: "create-and-edit-configurable-reports-checkbox",
                        get checkboxPermission() {
                            return self.role.permissions.edit_ucrs;
                        },
                        set checkboxPermission(value) {
                            self.role.permissions.edit_ucrs = value;
                        },
                        checkboxText: gettext("Allow role to create and edit custom web reports."),
                    });
                } else { //TODO: only text is different? Can I make it a get instead?
                    this.reports.push({
                        get visibilityRestraint() {
                            return self.role.permissions.access_all_locations;
                        },
                        text: gettext("Create and Edit Configurable Reports"),
                        checkboxLabel: "create-and-edit-configurable-reports-checkbox",
                        get checkboxPermission() {
                            return self.role.permissions.edit_ucrs;
                        },
                        set checkboxPermission(value) {
                            self.role.permissions.edit_ucrs = value;
                        },
                        checkboxText: gettext("Allow role to create and edit configurable reports."),
                    });
                }
            }
            const hasEmbeddedTableau = toggles.toggleEnabled("EMBEDDED_TABLEAU");
            this.reports.push({
                visibilityRestraint: true,
                text: hasEmbeddedTableau ? gettext("Access All CommCare Reports") : gettext("Access All Reports"),
                checkboxLabel: "access-all-reports-checkbox",
                get checkboxPermission() {
                    return self.reportPermissions.all;
                },
                set checkboxPermission(value) {
                    self.reportPermissions.all = value;
                },
                checkboxText: hasEmbeddedTableau
                    ? gettext("Allow role to view all CommCare reports. Excludes embedded Tableau reports")
                    : gettext("Allow role to access all reports."),
            });

            this.reports.push({
                get visibilityRestraint() {
                    return self.reportPermissions.all || _.any(self.reportPermissions.specific, (p) => p.value);
                },
                text: gettext("Download and Email Reports"),
                checkboxLabel: "download-and-email-reports-checkbox",
                get checkboxPermission() {
                    return self.role.permissions.download_reports;
                },
                set checkboxPermission(value) {
                    self.role.permissions.download_reports = value;
                },
                checkboxText: gettext("Allow role to download and email report data."),
            });
            if (toggles.toggleEnabled('EMBEDDED_TABLEAU')) {
                this.reports.push({
                    visibilityRestraint: true,
                    text: gettext("Access All Tableau Reports"),
                    checkboxLabel: "view-tableau-checkbox",
                    get checkboxPermission() {
                        return self.tableauPermissions.all;
                    },
                    set checkboxPermission(value) {
                        self.tableauPermissions.all = value;
                    },
                    checkboxText: gettext("Allow role to access all embedded Tableau reports."),
                });
            }

            this.webAppsPermissions = selectPermissionModel({
                text: gettext("Use Web Apps for online data entry"),
                listHeading: gettext("Select which web apps..."),
                showAlreadyConfiguredWarning: initialPageData.get('has_restricted_application_access'),
                permissionObj: self.role.permissions,
                accessKey: 'access_web_apps',
                listKey: 'web_apps_list',
                listChoices: initialPageData.get("web_apps_choices")
            });

            this.registryPermissions = [
                selectPermissionModel({
                    text: gettext("Manage Registries"),
                    listHeading: gettext("Select which registries the role can manage:"),
                    permissionObj: self.role.permissions,
                    accessKey: 'manage_data_registry',
                    listKey: 'manage_data_registry_list',
                    listChoices: initialPageData.get("data_registry_choices")
                }),
                selectPermissionModel({
                    text: gettext("View Registry Data"),
                    listHeading: gettext("Select which registry data the role can view:"),
                    permissionObj: self.role.permissions,
                    accessKey: 'view_data_registry_contents',
                    listKey: 'view_data_registry_contents_list',
                    listChoices: initialPageData.get("data_registry_choices")
                }),
            ];

            this.commcareAnalyticsRoles = {
                get all() {
                    return self.role.permissions.commcare_analytics_roles;
                },
                set all(checked) {
                    self.role.permissions.commcare_analytics_roles = checked;
                    if (checked) {
                        self.role.permissions.commcare_analytics_roles_list = [];
                    } else {
                        self.role.permissions.commcare_analytics_roles_list = [...this.specificCache];
                    }
                },
                specificCache: [...self.role.permissions.commcare_analytics_roles_list],

            };
            this.commcareAnalyticsRoles.specific = _.map(initialPageData.get('commcare_analytics_roles'), (role) => ({
                name: role.name,
                slug: role.slug,
                get value() {
                    return self.role.permissions.commcare_analytics_roles_list.indexOf(role.slug) !== -1;
                },
                set value(checked) {
                    if (checked) {
                        self.role.permissions.commcare_analytics_roles_list.push(this.slug);
                        this.commcareAnalyticsRoles.specificCache.push(this.slug);
                    } else {
                        removeItem(self.role.permissions.commcare_analytics_roles_list, this.slug);
                        removeItem(this.commcareAnalyticsRoles.specificCache, this.slug);
                    }
                }
            }));

            this.saveRole = () => {
                self.isSaving = true;

                console.log(`saveRole: ${JSON.stringify(self.role, null, 2)}`);

                $.ajax({
                    method: 'POST',
                    url: initialPageData.reverse("post_user_role"),
                    data: JSON.stringify(self.role, null, 2),
                    dataType: 'json',
                    success: () => {
                        self.isSaving = false;
                    },
                    error: (response) => {
                        self.isSaving = false;
                        let message = gettext("An error occurred, please try again.");
                        if (response.responseJSON && response.responseJSON.message) {
                            message = response.responseJSON.message;
                        }
                        self.roleError = message;
                    },
                });
            }
        }, // end init
    };
});

Alpine.start();
