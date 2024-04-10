hqDefine('users/js/roles',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/toggles',
    'hqwebapp/js/bootstrap3/alert_user',
    'hqwebapp/js/privileges',
], function ($, _, ko, toggles, alertUser, privileges) {
    let selectPermissionModel = function (id, permissionModel, text) {
        /*
        Function to build the view model for permissions that aren't simple booleans. The data is
        modelled as a boolean and a list. If the boolean is 'true' the user has access to all items.
        If the boolean is 'false' the user only has access to items selected in the list.

        This view model gives the user the ability to select 'none', 'all' or 'only selected'.

        Parameters:
          id: unique permission ID
          permissionModel: object the following keys:
            all: observable boolean
            specific: observable array of items which can be selected. Each item is expected
                to have at least 'name', 'slug' and 'value' fields.
          text: Text to display to the user. (see text defaults below)
         */
        text = _.defaults(text, {
            permissionText: 'Change me',
            accessNoneText: gettext("No Access"),
            accessAllText: gettext("Access All"),
            accessSelectedText: gettext("Access Selected"),
            listHeading: gettext("Select which items the role can access:"),
        });
        const [NONE, ALL, SELECTED] = ["none", "all", "selected"];
        const selectOptions = [
            {text: text.accessNoneText, value: NONE},
            {text: text.accessAllText, value: ALL},
            {text: text.accessSelectedText, value: SELECTED},
        ];
        let self = {
            id: id,
            text: text.permissionText,
            listHeading: text.listHeading,
            options: selectOptions,
            selection: ko.observable(),
            all: permissionModel.all,
            specific: permissionModel.specific,
        };
        self.showItems = ko.pureComputed(() =>{
            return self.selection() === SELECTED;
        });

        // set value of selection based on initial data
        if (self.all()) {
            self.selection(ALL);
        } else if (_.find(permissionModel.specific(), item => item.value())) {
            self.selection(SELECTED);
        } else {
            self.selection(NONE);
        }

        self.selection.subscribe(() => {
            // update permission data based on selection
            if (self.selection() === ALL) {
                self.all(true);
                self.specific().forEach(item => item.value(false));
                return;
            }
            self.all(false);
            if (self.selection() === NONE) {
                self.specific().forEach(item => item.value(false));
            }
        });

        self.hasError = ko.pureComputed(() => {
            return self.selection() === SELECTED && permissionModel.filteredSpecific().length === 0;
        });
        return self;
    };

    var RolesViewModel = function (o) {
        'use strict';
        var self, root;
        self = root = {};

        var UserRole = {
            wrap: function (data) {
                var cls = this;
                var self;

                data.reportPermissions = {
                    all: data.permissions.view_reports,
                    specific: ko.utils.arrayMap(root.reportOptions, function (report) {
                        return {
                            path: report.path,
                            slug: report.slug,
                            name: report.name,
                            value: data.permissions.view_report_list.indexOf(report.path) !== -1,
                        };
                    }),
                };

                data.tableauPermissions = {
                    all: data.permissions.view_tableau,
                    specific: ko.utils.arrayMap(root.tableauOptions, function (viz) {
                        var slug = String(viz.id);     // ultimately jsonobject expects this to be a string
                        return {
                            slug: slug,
                            name: viz.name,
                            value: data.permissions.view_tableau_list.indexOf(slug) !== -1,
                        };
                    }),
                };

                data.accessWebAppsPermission = {
                    all: data.permissions.access_web_apps,
                    specific: ko.utils.arrayMap(root.webAppsChoices, function (app) {
                        return {
                            slug: app._id,
                            name: app.name,
                            value: data.permissions.web_apps_list.indexOf(app._id) !== -1,
                        };
                    }),
                };

                data.manageRegistryPermission = {
                    all: data.permissions.manage_data_registry,
                    specific: ko.utils.arrayMap(root.dataRegistryChoices, function (registry) {
                        return {
                            name: registry.name,
                            slug: registry.slug,
                            value: data.permissions.manage_data_registry_list.indexOf(registry.slug) !== -1,
                        };
                    }),
                };

                data.viewRegistryContentsPermission = {
                    all: data.permissions.view_data_registry_contents,
                    specific: ko.utils.arrayMap(root.dataRegistryChoices, function (registry) {
                        return {
                            name: registry.name,
                            slug: registry.slug,
                            value: data.permissions.view_data_registry_contents_list.indexOf(registry.slug) !== -1,
                        };
                    }),
                };

                data.manageRoleAssignments = {
                    all: data.is_non_admin_editable,
                    specific: ko.utils.arrayMap(o.nonAdminRoles, function (role) {
                        return {
                            path: role._id,
                            name: role.name,
                            value: data.assignable_by.indexOf(role._id) !== -1,
                        };
                    }),
                };

                self = ko.mapping.fromJS(data);
                let filterSpecific = (permissions) => {
                    return ko.computed(function () {
                        return ko.utils.arrayFilter(permissions.specific(), function (item) {
                            return item.value();
                        });
                    });
                };
                self.isEditable = ko.computed(function () {
                    return root.allowEdit && (!self.upstream_id() || root.unlockLinkedRoles());
                });
                self.reportPermissions.filteredSpecific = filterSpecific(self.reportPermissions);
                self.tableauPermissions.filteredSpecific = filterSpecific(self.tableauPermissions);
                self.accessWebAppsPermission.filteredSpecific = filterSpecific(self.accessWebAppsPermission);
                self.manageRegistryPermission.filteredSpecific = filterSpecific(self.manageRegistryPermission);
                self.viewRegistryContentsPermission.filteredSpecific = filterSpecific(self.viewRegistryContentsPermission);
                self.canSeeAnyReports = ko.computed(function () {
                    return self.reportPermissions.all() || _.any(self.reportPermissions.specific(), (p) => p.value());
                });

                self.unwrap = function () {
                    return cls.unwrap(self);
                };
                self.preventRoleDelete = data.preventRoleDelete;
                self.hasUnpermittedLocationRestriction = data.has_unpermitted_location_restriction || false;
                if (self.hasUnpermittedLocationRestriction) {
                    self.permissions.access_all_locations(true);
                }
                self.accessAreas = [
                    {
                        showOption: self.permissions.access_all_locations,
                        editPermission: self.permissions.edit_web_users,
                        viewPermission: self.permissions.view_web_users,
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
                        showOption: true,
                        editPermission: self.permissions.edit_commcare_users,
                        viewPermission: self.permissions.view_commcare_users,
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
                        showOption: self.permissions.access_all_locations,
                        editPermission: self.permissions.edit_groups,
                        viewPermission: self.permissions.view_groups,
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
                        allowCheckboxPermission: self.permissions.edit_users_in_groups,
                    },
                    {
                        showOption: true,
                        editPermission: self.permissions.edit_locations,
                        viewPermission: self.permissions.view_locations,
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
                        allowCheckboxPermission: self.permissions.edit_users_in_locations,
                    },
                    {
                        showOption: privileges.hasPrivilege('data_dictionary'),
                        editPermission: self.permissions.edit_data_dict,
                        viewPermission: self.permissions.view_data_dict,
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
                        editPermission: self.permissions.edit_data,
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
                        editPermission: self.permissions.edit_messaging,
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
                        showOption: ko.pureComputed(function () {
                            return self.permissions.access_all_locations() || self.permissions.access_api();
                        }),
                        editPermission: self.permissions.access_api,
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
                        showOption: self.permissions.access_all_locations,
                        editPermission: self.permissions.edit_apps,
                        viewPermission: self.permissions.view_apps,
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
                        showOption: self.permissions.access_all_locations,
                        editPermission: function () {return false;},
                        viewPermission: self.permissions.view_roles,
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
                        showOption: root.DataFileDownloadEnabled,
                        editPermission: self.permissions.edit_file_dropzone,
                        viewPermission: self.permissions.view_file_dropzone,
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
                        showOption: root.ExportOwnershipEnabled,
                        editPermission: self.permissions.edit_shared_exports,
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
                        showOption: root.attendanceTrackingPrivilege,
                        editPermission: self.permissions.manage_attendance_tracking,
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
                ];

                var hasEmbeddedTableau = toggles.toggleEnabled("EMBEDDED_TABLEAU");

                const linkedTitle = root.ermPrivilege ?
                    gettext("Enterprise Release Management") : gettext("Multi-Environment Release Management");
                self.erm = {
                    'title': linkedTitle,
                    'visible': root.ermPrivilege || root.mrmPrivilege,
                    'access_release_management': {
                        text: gettext('Linked Project Spaces'),
                        checkboxLabel: "erm-checkbox",
                        checkboxPermission: self.permissions.access_release_management,
                        checkboxText: gettext("Allow role to configure linked project spaces"),
                    },
                    'edit_linked_configs': {
                        text: gettext("Linked Configurations"),
                        checkboxLabel: "erm-edit-linked-checkbox",
                        checkboxPermission: self.permissions.edit_linked_configurations,
                        checkboxText: gettext("Allow role to edit linked configurations on this project space"),
                    },
                };

                self.reports = [
                    {
                        visibilityRestraint: self.permissions.access_all_locations,
                        text: gettext("Create and Edit Reports"),
                        checkboxLabel: "create-and-edit-reports-checkbox",
                        checkboxPermission: self.permissions.edit_reports,
                        checkboxText: gettext("Allow role to create and edit reports in report builder."),
                    },
                ];
                if (toggles.toggleEnabled('USER_CONFIGURABLE_REPORTS')) {
                    if (toggles.toggleEnabled('UCR_UPDATED_NAMING')) {
                        self.reports.push({
                            visibilityRestraint: self.permissions.access_all_locations,
                            text: gettext("Create and Edit Custom Web Reports"),
                            checkboxLabel: "create-and-edit-configurable-reports-checkbox",
                            checkboxPermission: self.permissions.edit_ucrs,
                            checkboxText: gettext("Allow role to create and edit custom web reports."),
                        });
                    } else {
                        self.reports.push({
                            visibilityRestraint: self.permissions.access_all_locations,
                            text: gettext("Create and Edit Configurable Reports"),
                            checkboxLabel: "create-and-edit-configurable-reports-checkbox",
                            checkboxPermission: self.permissions.edit_ucrs,
                            checkboxText: gettext("Allow role to create and edit configurable reports."),
                        });
                    }
                }
                self.reports.push({
                    visibilityRestraint: true,
                    text: hasEmbeddedTableau ? gettext("Access All CommCare Reports") : gettext("Access All Reports"),
                    checkboxLabel: "access-all-reports-checkbox",
                    checkboxPermission: self.reportPermissions.all,
                    checkboxText: hasEmbeddedTableau
                        ? gettext("Allow role to view all CommCare reports. Excludes embedded Tableau reports")
                        : gettext("Allow role to access all reports."),
                });
                self.reports.push({
                    visibilityRestraint: self.canSeeAnyReports,
                    text: gettext("Download and Email Reports"),
                    checkboxLabel: "download-and-email-reports-checkbox",
                    checkboxPermission: self.permissions.download_reports,
                    checkboxText: gettext("Allow role to download and email report data."),
                });
                if (toggles.toggleEnabled('EMBEDDED_TABLEAU')) {
                    self.reports.push({
                        visibilityRestraint: true,
                        text: gettext("Access All Tableau Reports"),
                        checkboxLabel: "view-tableau-checkbox",
                        checkboxPermission: self.tableauPermissions.all,
                        checkboxText: gettext("Allow role to access all embedded Tableau reports."),
                    });
                }
                self.registryPermissions = [
                    selectPermissionModel(
                        'manage_registries',
                        self.manageRegistryPermission,
                        {
                            permissionText: gettext("Manage Registries"),
                            listHeading: gettext("Select which registries the role can manage:"),
                        }
                    ),
                    selectPermissionModel(
                        'view_registry_contents',
                        self.viewRegistryContentsPermission,
                        {
                            permissionText: gettext("View Registry Data"),
                            listHeading: gettext("Select which registry data the role can view:"),
                        }
                    ),
                ];

                self.webAppsPermissions = selectPermissionModel(
                    'access_web_apps',
                    self.accessWebAppsPermission,
                    {
                        permissionText: gettext("Use Web Apps for online data entry"),
                        listHeading: gettext("Select which web apps the role has access to:"),
                    }
                );

                // Automatically disable "Access APIs" when "Full Organization Access" is disabled
                self.permissions.access_all_locations.subscribe(() => {
                    if (!self.permissions.access_all_locations() && self.permissions.access_api()) {
                        self.permissions.access_api(false);
                    }
                });

                self.validate = function () {
                    let permissionsToValidate = self.registryPermissions.concat(self.webAppsPermissions);
                    permissionsToValidate.forEach((perm) => {
                        if (perm.hasError()) {
                            throw interpolate(
                                gettext('Select at least one item from the list for "%s"'),
                                [perm.text]
                            );
                        }
                    });
                };

                return self;
            },
            unwrap: function (self) {
                var data = ko.mapping.toJS(self);

                if (data.name) {
                    data.name = data.name.trim();
                }

                const unwrapItemList = function (items, itemAttr = 'slug') {
                    return ko.utils.arrayMap(ko.utils.arrayFilter(items, function (item) {
                        return item.value;
                    }), function (item) {
                        return item[itemAttr];
                    });
                };

                data.permissions.view_reports = data.reportPermissions.all;
                data.permissions.view_report_list = unwrapItemList(data.reportPermissions.specific, 'path');
                data.permissions.view_tableau = data.tableauPermissions.all;
                data.permissions.view_tableau_list = unwrapItemList(data.tableauPermissions.specific);

                data.permissions.manage_data_registry = data.manageRegistryPermission.all;
                data.permissions.manage_data_registry_list = unwrapItemList(data.manageRegistryPermission.specific);

                data.permissions.view_data_registry_contents = data.viewRegistryContentsPermission.all;
                data.permissions.view_data_registry_contents_list = unwrapItemList(
                    data.viewRegistryContentsPermission.specific);

                data.permissions.access_web_apps = data.accessWebAppsPermission.all;
                data.permissions.web_apps_list = unwrapItemList(data.accessWebAppsPermission.specific);

                data.is_non_admin_editable = data.manageRoleAssignments.all;
                data.assignable_by = unwrapItemList(data.manageRoleAssignments.specific, 'path');
                return data;
            },
        };

        self.DataFileDownloadEnabled = o.DataFileDownloadEnabled;
        self.ExportOwnershipEnabled = o.ExportOwnershipEnabled;
        self.allowEdit = o.allowEdit;
        self.reportOptions = o.reportOptions;
        self.tableauOptions = o.tableauOptions;
        self.canRestrictAccessByLocation = o.canRestrictAccessByLocation;
        self.landingPageChoices = o.landingPageChoices;
        self.dataRegistryChoices = o.dataRegistryChoices;
        self.webAppsChoices = o.webAppsChoices;
        self.ermPrivilege = o.ermPrivilege;
        self.mrmPrivilege = o.mrmPrivilege;
        self.attendanceTrackingPrivilege = o.attendanceTrackingPrivilege;
        self.unlockLinkedRoles = ko.observable(false);
        self.canEditLinkedData = o.canEditLinkedData;

        self.userRoles = ko.observableArray(ko.utils.arrayMap(o.userRoles, function (userRole) {
            return UserRole.wrap(userRole);
        }));
        self.roleBeingEdited = ko.observable();
        self.roleBeingDeleted = ko.observable();
        self.defaultRole = UserRole.wrap(o.defaultRole);

        self.hasLinkedRoles = ko.computed(function () {
            return self.userRoles().some(element => element.upstream_id());
        });

        self.toggleLinkedRoles = function () {
            self.unlockLinkedRoles(!self.unlockLinkedRoles());
        };

        self.addOrReplaceRole = function (role) {
            var newRole = UserRole.wrap(role);
            var i;
            for (i = 0; i < self.userRoles().length; i++) {
                if (ko.utils.unwrapObservable(self.userRoles()[i]._id) === newRole._id()) {
                    self.userRoles.splice(i, 1, newRole);
                    return;
                }
            }
            self.userRoles.push(newRole);
        };

        self.removeRole = function (role) {
            var i;
            for (i = 0; i < self.userRoles().length; i++) {
                if (ko.utils.unwrapObservable(self.userRoles()[i]._id) === role._id) {
                    self.userRoles.splice(i, 1);
                    return;
                }
            }
        };

        self.setRoleBeingEdited = function (role) {
            var actionType = self.allowEdit ? gettext("Edit Role: ") : gettext("View Role: ");
            var title = role === self.defaultRole ? gettext("New Role") : actionType + role.name();
            var roleCopy = UserRole.wrap(UserRole.unwrap(role));
            roleCopy.modalTitle = title;
            self.roleBeingEdited(roleCopy);
        };
        self.unsetRoleBeingEdited = function () {
            self.roleBeingEdited(undefined);
        };
        self.setRoleBeingDeleted = function (role) {
            if (!role._id || !role.preventRoleDelete) {
                var title = gettext("Delete Role: ") + role.name();
                var context = {role: role.name()};
                var modalConfirmation = _.template(gettext(
                    "Are you sure you want to delete the role <%- role %>?"
                ))(context);
                var roleCopy = UserRole.wrap(UserRole.unwrap(role));

                roleCopy.modalTitle = title;
                roleCopy.modalConfirmation = modalConfirmation;
                self.roleBeingDeleted(roleCopy);
                self.modalDeleteButton.state('save');
            }
        };
        self.unsetRoleBeingDeleted = function () {
            self.roleBeingDeleted(undefined);
        };
        self.modalDeleteButton = {
            state: ko.observable(),
            saveOptions: function () {
                return {
                    url: o.deleteUrl,
                    type: 'post',
                    data: JSON.stringify(UserRole.unwrap(self.roleBeingDeleted)),
                    dataType: 'json',
                    success: function (data) {
                        self.removeRole(data);
                        self.unsetRoleBeingDeleted();
                    },
                };
            },
        };
        self.roleError = ko.observable("");
        self.setRoleError = function (form, error) {
            self.roleError(error);
            setTimeout(() => {
                $(form).find('[type="submit"]').enableButton();
            }, 100);
        };
        self.clearRoleError = function () {
            self.roleError("");
        };
        self.clearRoleForm = function () {
            self.clearRoleError();
            self.unsetRoleBeingEdited();
        };
        self.submitNewRole = function (form) {
            self.clearRoleError();
            try {
                self.roleBeingEdited().validate();
            } catch (e) {
                self.setRoleError(form, e);
                return;
            }
            $.ajax({
                method: 'POST',
                url: o.saveUrl,
                data: JSON.stringify(UserRole.unwrap(self.roleBeingEdited)),
                dataType: 'json',
                success: function (data) {
                    self.addOrReplaceRole(data);
                    self.unsetRoleBeingEdited();
                },
                error: function (response) {
                    var message = gettext("An error occurred, please try again.");
                    if (response.responseJSON && response.responseJSON.message) {
                        message = response.responseJSON.message;
                    }
                    self.setRoleError(form, message);
                },
            });
        };

        return self;
    };

    return {
        initUserRoles: function ($element, $modal, $infoBar, o) {
            const viewModel = RolesViewModel(o);
            $element.each(function () {
                $element.koApplyBindings(viewModel);
            });
            $modal.koApplyBindings(viewModel);
            $infoBar.koApplyBindings(viewModel);
        },
    };
});
