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
                return self;
            },
            unwrap: function (self) {
                var data = ko.mapping.toJS(self);

                if (data.name) {
                    // some older browsers don't use the String.prototype.trim() function. Explicity declare it in this case:
                    if (!String.prototype.trim) {
                        String.prototype.trim = function () {
                            return this.replace(/^\s+|\s+$/g,'');
                        };
                    }
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
