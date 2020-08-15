hqDefine('users/js/roles',[
    'jquery',
    'knockout',
    'hqwebapp/js/alert_user',
], function ($, ko, alertUser) {
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

                data.webAppsPermissions = {
                    all: data.permissions.view_web_apps,
                    specific: ko.utils.arrayMap(root.webAppsList, function (app) {
                        return {
                            path: app._id,
                            name: app.name,
                            value: data.permissions.view_web_apps_list.indexOf(app._id) !== -1,
                        };
                    }),
                };

                data.manageAppReleasePermissions = {
                    all: data.permissions.manage_releases,
                    specific: ko.utils.arrayMap(root.appsList, function (app) {
                        return {
                            path: app._id,
                            name: app.name,
                            value: data.permissions.manage_releases_list.indexOf(app._id) !== -1,
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
                    editPermission: self.permissions.edit_web_users,
                    viewPermission: self.permissions.view_web_users,
                    text:  "<strong>Web Users</strong> &mdash; invite new web users, manage account settings, remove membership",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-web-users-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-web-users-checkbox",
                    srEditAndViewText: "Edit & View Mobile Workers",
                    srViewOnlyText: "View-Only Mobile Workers",
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    editPermission: self.permissions.edit_commcare_users,
                    viewPermission: self.permissions.view_commcare_users,
                    text:  "<strong>Mobile Workers</strong> &mdash; create new accounts, manage account settings,deactivate or delete mobile workers. This permission also allows users to login as any mobile worker in Web Apps.",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-commcare-users-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-commcare-users-checkbox",
                    srEditAndViewText: "Edit & View Web Users",
                    srViewOnlyText: "View-Only Web Users",
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    editPermission: self.permissions.edit_groups,
                    viewPermission: self.permissions.view_groups,
                    text:  "<strong>Groups</strong> &mdash; manage groups of mobile workers",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-groups-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-groups-checkbox",
                    srEditAndViewText: "Edit & View Groups",
                    srViewOnlyText: "View-Only Web Groups",
                    showAllowCheckbox: true,
                    allowCheckboxText: "Allow changing group membership (requires edit groups).",
                    allowCheckboxId: "edit-users-groups-checkbox",
                    allowCheckboxPermission: self.permissions.edit_users_in_groups,
                },
                {
                    editPermission: self.permissions.edit_locations,
                    viewPermission: self.permissions.view_locations,
                    text:  "<strong>Locations</strong> &mdash; manage locations in the Organization's Hierarchy",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-locations-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-locations-checkbox",
                    srEditAndViewText: "Edit & View Locations",
                    srViewOnlyText: "View-Only Web Locations",
                    showAllowCheckbox: true,
                    allowCheckboxText: "Allow changing workers at a location.",
                    allowCheckboxId: "edit-users-locations-checkbox",
                    allowCheckboxPermission: self.permissions.edit_users_in_locations,
                },
                {
                    editPermission: self.permissions.edit_data,
                    viewPermission: null,
                    text:  "<strong>Data</strong> &mdash; view, export, and edit form and case data, reassign cases",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-data-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-data-checkbox",
                    srEditAndViewText: "Edit & View Data",
                    srViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    editPermission: self.permissions.access_web_apps,
                    viewPermission: null,
                    text:  "<strong>Web Apps</strong> &mdash; use Web Apps for online data entry",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-web-apps-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-web-apps-checkbox",
                    srEditAndViewText: "Access Web Apps",
                    srViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    editPermission: self.permissions.access_api,
                    viewPermission: null,
                    text:  "<strong>Access APIs</strong> &mdash; use CommCare HQ APIs to read and update data. Specific APIs may require additional permissions.",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-apis-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-apis-checkbox",
                    srEditAndViewText: "Access APIs",
                    srViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    editPermission: self.permissions.edit_apps,
                    viewPermission: null,
                    text:  "<strong>Applications</strong> &mdash; modify or view the structure and configuration of all applications.",
                    showEditCheckbox: true,
                    editCheckboxLabel: "edit-apps-checkbox",
                    showViewCheckbox: false,
                    viewCheckboxLabel: "view-apps-checkbox",
                    srEditAndViewText: "Edit & View Apps",
                    srViewOnlyText: null,
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                },
                {
                    editPermission: self.permissions.view_roles,
                    viewPermission: null,
                    text:  "<strong>Roles &amp; Permissions</strong> &mdash; view web user and mobile worker roles &amp; permissions (only Admins can edit roles)",
                    showEditCheckbox: false,
                    editCheckboxLabel: "edit-roles-checkbox",
                    showViewCheckbox: true,
                    viewCheckboxLabel: "view-roles-checkbox",
                    srEditAndViewText: null,
                    srViewOnlyText: "View Roles and Permssions",
                    showAllowCheckbox: false,
                    allowCheckboxText: null,
                    allowCheckboxId: null,
                    allowCheckboxPermission: null,
                }];

                self.reports = [
                {
                    visibilityRestraint: self.permissions.access_all_locations,
                    text: "Create and Edit Reports",
                    checkboxLabel: "create-and-edit-reports-checkbox",
                    checkboxPermission: self.permissions.edit_reports,
                    checkboxText: "Allow role to create and edit reports in report builder.",
                },
                {
                    visibilityRestraint: true,
                    text: "Access All Reports",
                    checkboxLabel: "access-all-reports-checkbox",
                    checkboxPermission: self.reportPermissions.all,
                    checkboxText: "Allow role to access all reports.",
                },
                ]

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

                data.permissions.view_web_apps = data.webAppsPermissions.all;
                data.permissions.view_web_apps_list = ko.utils.arrayMap(ko.utils.arrayFilter(data.webAppsPermissions.specific, function (app) {
                    return app.value;
                }), function (app) {
                    return app.path;
                });
                data.permissions.manage_releases = data.manageAppReleasePermissions.all;
                data.permissions.manage_releases_list = ko.utils.arrayMap(ko.utils.arrayFilter(data.manageAppReleasePermissions.specific, function (app) {
                    return app.value;
                }), function (app) {
                    return app.path;
                });
                data.is_non_admin_editable = data.manageRoleAssignments.all;
                data.assignable_by = ko.utils.arrayMap(ko.utils.arrayFilter(data.manageRoleAssignments.specific, function (role) {
                    return role.value;
                }), function (role) {
                    return role.path;
                });
                return data;
            },
        };

        self.allowEdit = o.allowEdit;
        self.reportOptions = o.reportOptions;
        self.webAppsList = o.webAppsList;
        self.appsList = o.appsList;
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
            console.log(roleCopy);
            console.log(roleCopy.uiInfo);
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
                    "Are you sure you want to delete the role <%= role %>?"
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
