import _ from "underscore";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";

const getOptionNames = function (slugs, options, slugProperty = 'slug') {
    return _.map(slugs, function (slug) {
        const query = {};
        query[slugProperty] = slug;
        const match = _.find(options, query);
        return match ? match.name : slug;
    });
};

var RolesViewModel = function (o) {
    var self;
    self = {};

    self.allowEdit = o.allowEdit;

    self.userRoles = ko.observableArray(o.userRoles.map(function (role) {
        role.preventRoleDelete = role.preventRoleDelete || false;
        role.isEditable = role.isEditable !== undefined ? role.isEditable : true;
        role.manage_data_registry_list =
            getOptionNames(role.permissions.manage_data_registry_list, initialPageData.get("data_registry_choices"));
        role.view_data_registry_contents_list =
            getOptionNames(role.permissions.view_data_registry_contents_list, initialPageData.get("data_registry_choices"));
        role.view_report_list =
            getOptionNames(role.permissions.view_report_list, initialPageData.get("report_list"), 'path');
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
