hqDefine('users/js/roles',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/alert_user',
], function ($, _, ko, alertUser) {
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
                        text: gettext("Download and Email Reports"),
                        checkboxLabel: "download-and-email-reports-checkbox",
                        checkboxPermission: self.permissions.download_reports,
                        checkboxText: gettext("Allow role to download and email reports and " +
                            "create scheduled reports."),
                    },
                    {
                        visibilityRestraint: true,
                        text: gettext("Access All Reports"),
                        checkboxLabel: "access-all-reports-checkbox",
                        checkboxPermission: self.reportPermissions.all,
                        checkboxText: gettext("Allow role to access all reports."),
                    }];

                return self;
            },
            unwrap: function (self) {
                var data = ko.mapping.toJS(self);

                if (data.name) {
                    data.name = data.name.trim();
                }

                data.permissions.view_report_list = ko.utils.arrayMap(ko.utils.arrayFilter(data.reportPermissions.specific, function (report) {
                    return report.value;
                }), function (report) {
                    return report.path;
                });
                data.permissions.view_reports = data.reportPermissions.all;
                data.is_non_admin_editable = data.manageRoleAssignments.all;
                data.assignable_by = ko.utils.arrayMap(ko.utils.arrayFilter(data.manageRoleAssignments.specific, function (role) {
                    return role.value;
                }), function (role) {
                    return role.path;
                });
                return data;
            },
        };

        self.DataFileDownloadEnabled = o.DataFileDownloadEnabled;
        self.ExportOwnershipEnabled = o.ExportOwnershipEnabled;
        self.allowEdit = o.allowEdit;
        self.reportOptions = o.reportOptions;
        self.canRestrictAccessByLocation = o.canRestrictAccessByLocation;
        self.landingPageChoices = o.landingPageChoices;
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
        self.unsetRoleBeingEdited = function () {
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
        self.submitNewRole = function () {
            // moved saveOptions inline
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
                    alertUser.alert_user(response.responseJSON.message, 'danger');
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
