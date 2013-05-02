$(function () {
    function RolesViewModel(o) {
        var self = this,
            root = this;

        var UserRole = {
            wrap: function (data) {
                var cls = this;
                var self;

                data.reportPermissions = {
                    all: data.permissions.view_reports,
                    specific: ko.utils.arrayMap(root.reportOptions, function (report) {
                        return {
                            path: report.path,
                            name: report.name,
                            value: data.permissions.view_report_list.indexOf(report.path) !== -1
                        };
                    })
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
                return self;
            },
            unwrap: function (self) {
                var data = ko.mapping.toJS(self);

                data.permissions.view_report_list = ko.utils.arrayMap(ko.utils.arrayFilter(data.reportPermissions.specific, function (report) {
                    return report.value;
                }), function (report) {
                    return report.path;
                });
                data.permissions.view_reports = data.reportPermissions.all;
                return data;
            }
        };

        function wrapRole(role) {
            role.permissions.viewReportList = ko.computed({
                read: function () {
                    return ko.utils.arrayMap(role.permissions.view_report_list(), function (reportPath) {
                        return self.getReportObject(reportPath);
                    });
                },
                write: function (reports) {
                    var reportPaths = ko.utils.arrayMap(reports, function (report) {
                        return report.path;
                    });
                    role.permissions.view_report_list.removeAll();
                    ko.utils.arrayForEach(reportPaths, function (path) {
                        role.permissions.view_report_list.push(path);
                    });
                }
            });
        }
        self.allowEdit = o.allowEdit;
        self.reportOptions = o.reportOptions;
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
        self.defaultRole = UserRole.wrap(o.defaultRole);

        self.addOrReplaceRole = function (role) {
            var newRole = UserRole.wrap(role);
            wrapRole(newRole);
            var i;
            for (i = 0; i < self.userRoles().length; i++) {
                if (ko.utils.unwrapObservable(self.userRoles()[i]._id) === newRole._id()) {
                    self.userRoles.splice(i, 1, newRole);
                    return;
                }
            }
            self.userRoles.push(newRole);
        };

        self.setRoleBeingEdited = function (role) {
            var title = role === self.defaultRole ? "New Role" : "Edit Role: " + role.name();
            var roleCopy = UserRole.wrap(UserRole.unwrap(role));
            roleCopy.modalTitle = title;
            self.roleBeingEdited(roleCopy);
            self.modalSaveButton.state('save');
        };
        self.unsetRoleBeingEdited = function () {
            self.roleBeingEdited(undefined);
        };
        self.modalSaveButton = {
            state: ko.observable(),
            saveOptions: function () {
                return {
                    url: o.saveUrl,
                    type: 'post',
                    data: JSON.stringify(UserRole.unwrap(self.roleBeingEdited)),
                    dataType: 'json',
                    success: function (data) {
                        self.addOrReplaceRole(data);
                        self.unsetRoleBeingEdited();
                    }
                };
            }
        }

    }
    $.fn.userRoles = function (o) {
        this.each(function () {
            ko.applyBindings(new RolesViewModel(o), $(this).get(0));
        });
    };
}());