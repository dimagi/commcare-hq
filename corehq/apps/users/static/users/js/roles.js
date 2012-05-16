$(function () {
    function RolesViewModel(o) {
        var self = this;

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

        self.userRoles = ko.mapping.fromJS(o.userRoles);
        ko.utils.arrayForEach(self.userRoles(), function (role) {
            wrapRole(role);
        });
        self.roleBeingEdited = ko.observable();
        self.defaultRole = ko.mapping.fromJS(o.defaultRole);

        self.addOrReplaceRole = function (role) {
            var newRole = ko.mapping.fromJS(role);
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
            var roleCopy = ko.mapping.fromJS(ko.mapping.toJS(role));
            wrapRole(roleCopy);
            roleCopy.modalTitle = title;
            self.roleBeingEdited(roleCopy);
            self.modalSaveButton.fire('change');
        };
        self.unsetRoleBeingEdited = function () {
            self.roleBeingEdited(undefined);
        };
        self.modalSaveButton = SaveButton.init({
            save: function () {
                console.log(ko.mapping.toJSON(self.roleBeingEdited));
                console.log(o.saveUrl);
                self.modalSaveButton.ajax({
                    url: o.saveUrl,
                    type: 'post',
                    data: ko.mapping.toJSON(self.roleBeingEdited),
                    dataType: 'json',
                    success: function (data) {
                        self.addOrReplaceRole(data);
                        self.unsetRoleBeingEdited();
                    }
                });
            }
        });

    }
    $.fn.userRoles = function (o) {
        this.each(function () {
            ko.applyBindings(new RolesViewModel(o), $(this).get(0));
        });
    };
}());