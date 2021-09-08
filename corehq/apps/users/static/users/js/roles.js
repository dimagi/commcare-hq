hqDefine('users/js/roles',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/alert_user',
], function ($, _, ko, alertUser) {
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
        const [none, all, selected] = ["none", "all", "selected"];
        const selectOptions = [
            {text: text.accessNoneText, value: none},
            {text: text.accessAllText, value: all},
            {text: text.accessSelectedText, value: selected},
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
            return self.selection() === selected;
        });

        // set value of selection based on initial data
        if (self.all()) {
            self.selection(all);
        } else if (_.find(permissionModel.specific(), item => item.value())) {
            self.selection(selected)
        } else {
            self.selection(none);
        }

        self.selection.subscribe(() => {
            // update permission data based on selection
            if (self.selection() === all) {
                self.all(true);
                self.specific().forEach(item => item.value(false));
                return;
            }
            self.all(false);
            if (self.selection() === none) {
                self.specific().forEach(item => item.value(false));
            }
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
                self.reportPermissions.filteredSpecific = ko.computed(function () {
                    return ko.utils.arrayFilter(self.reportPermissions.specific(), function (report) {
                        return report.value();
                    });
                });
                self.unwrap = function () {
                    return cls.unwrap(self);
                };
                self.hasUsersAssigned = data.hasUsersAssigned;
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
                        text: gettext("<strong>Mobile Workers</strong> &mdash; create new accounts, manage account settings,deactivate or delete mobile workers."),
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
                        showOption: root.webAppsPrivilege,
                        editPermission: self.permissions.access_web_apps,
                        viewPermission: null,
                        text: gettext("<strong>Web Apps</strong> &mdash; use Web Apps for online data entry"),
                        showEditCheckbox: true,
                        editCheckboxLabel: "edit-web-apps-checkbox",
                        showViewCheckbox: false,
                        viewCheckboxLabel: "view-web-apps-checkbox",
                        screenReaderEditAndViewText: gettext("Access Web Apps"),
                        screenReaderViewOnlyText: null,
                        showAllowCheckbox: false,
                        allowCheckboxText: null,
                        allowCheckboxId: null,
                        allowCheckboxPermission: null,
                    },
                    {
                        showOption: true,
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
                        text: gettext("<strong>Shared Exports</strong> &mdash; access and edit the content and structure of shared exports"),
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
                    }];

                self.reports = [
                    {
                        visibilityRestraint: self.permissions.access_all_locations,
                        text: gettext("Create and Edit Reports"),
                        checkboxLabel: "create-and-edit-reports-checkbox",
                        checkboxPermission: self.permissions.edit_reports,
                        checkboxText: gettext("Allow role to create and edit reports in report builder."),
                    },
                    {
                        visibilityRestraint: true,
                        text: gettext("Access All Reports"),
                        checkboxLabel: "access-all-reports-checkbox",
                        checkboxPermission: self.reportPermissions.all,
                        checkboxText: gettext("Allow role to access all reports."),
                    }];

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
                            listHeading: gettext("Select which registries the role access:"),
                        }
                    ),
                ];

                return self;
            },
            unwrap: function (self) {
                var data = ko.mapping.toJS(self);

                if (data.name) {
                    data.name = data.name.trim();
                }

                const unWrapItemList = function (items, item_attr = 'slug') {
                    return ko.utils.arrayMap(ko.utils.arrayFilter(items, function (item) {
                        return item.value;
                    }), function (item) {
                        return item[item_attr];
                    });
                };

                data.permissions.view_reports = data.reportPermissions.all;
                data.permissions.view_report_list = unWrapItemList(data.reportPermissions.specific, 'path');

                data.permissions.manage_data_registry = data.manageRegistryPermission.all;
                data.permissions.manage_data_registry_list = unWrapItemList(data.manageRegistryPermission.specific);

                data.permissions.view_data_registry_contents = data.viewRegistryContentsPermission.all;
                data.permissions.view_data_registry_contents_list = unWrapItemList(
                    data.viewRegistryContentsPermission.specific);

                data.is_non_admin_editable = data.manageRoleAssignments.all;
                data.assignable_by = unWrapItemList(data.manageRoleAssignments.specific, 'path');
                return data;
            },
        };

        self.DataFileDownloadEnabled = o.DataFileDownloadEnabled;
        self.ExportOwnershipEnabled = o.ExportOwnershipEnabled;
        self.allowEdit = o.allowEdit;
        self.reportOptions = o.reportOptions;
        self.canRestrictAccessByLocation = o.canRestrictAccessByLocation;
        self.landingPageChoices = o.landingPageChoices;
        self.dataRegistryChoices = o.dataRegistryChoices;
        self.webAppsPrivilege = o.webAppsPrivilege;
        self.getReportObject = function (path) {
            var i;
            for (i = 0; i < self.reportOptions.length; i++) {
                if (self.reportOptions[i].path === path) {
                    return self.reportOptions[i];
                }
            }
            return path;
        };

        self.userRoles = ko.observableArray(ko.utils.arrayMap(o.userRoles, function (userRole) {
            return UserRole.wrap(userRole);
        }));
        self.roleBeingEdited = ko.observable();
        self.roleBeingDeleted = ko.observable();
        self.defaultRole = UserRole.wrap(o.defaultRole);

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
        self.unsetRoleBeingEdited = function (_, event) {
            self.roleBeingEdited(undefined);
        };
        self.setRoleBeingDeleted = function (role) {
            if (!role._id || !role.hasUsersAssigned) {
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
            $(form).find('[type="submit"]').enableButton();
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
                }
            });
        };

        return self;
    };

    return {
        initUserRoles: function ($element, o) {
            $element.each(function () {
                $element.koApplyBindings(RolesViewModel(o));
            });
        },
    };
});
