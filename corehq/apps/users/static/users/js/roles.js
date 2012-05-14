$(function () {
    function RolesViewModel(o) {
        var self = this;
        console.log(o.userRoles);
        self.userRoles = ko.mapping.fromJS(o.userRoles);
        self.roleBeingEdited = ko.observable();
        self.defaultRole = ko.mapping.fromJS(o.defaultRole);

        self.addOrReplaceRole = function (role) {
            var newRole = ko.mapping.fromJS(role);
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