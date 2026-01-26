import _ from "underscore";
import ko from "knockout";

var RolesViewModel = function (o) {
    var self;
    self = {};

    self.allowEdit = o.allowEdit;

    self.userRoles = ko.observableArray(o.userRoles.map(function (role) {
        role.preventRoleDelete = role.preventRoleDelete || false;
        role.isEditable = role.isEditable !== undefined ? role.isEditable : true;
        return role;
    }));
    self.roleBeingDeleted = ko.observable();

    self.removeRole = function (role) {
        var i;
        for (i = 0; i < self.userRoles().length; i++) {
            if (ko.utils.unwrapObservable(self.userRoles()[i]._id) === role._id) {
                self.userRoles.splice(i, 1);
                return;
            }
        }
    };

    self.setRoleBeingDeleted = function (role) {
        if (!role._id || !role.preventRoleDelete) {
            var title = gettext("Delete Role: ") + role.name();
            var context = {role: role.name()};
            var modalConfirmation = _.template(gettext(
                "Are you sure you want to delete the role <%- role %>?",
            ))(context);

            role.modalTitle = title;
            role.modalConfirmation = modalConfirmation;
            self.roleBeingDeleted(role);
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
                data: JSON.stringify(self.roleBeingDeleted),
                dataType: 'json',
                success: function (data) {
                    self.removeRole(data);
                    self.unsetRoleBeingDeleted();
                },
            };
        },
    };

    return self;
};

export default {
    initUserRoles: function ($element, $modal, $infoBar, o) {
        const viewModel = RolesViewModel(o);
        $element.each(function () {
            $element.koApplyBindings(viewModel);
        });
        $modal.koApplyBindings(viewModel);
        $infoBar.koApplyBindings(viewModel);
    },
};
