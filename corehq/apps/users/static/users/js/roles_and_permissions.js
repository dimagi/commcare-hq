import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import userRoles from "users/js/roles";
import "hqwebapp/js/bootstrap5/knockout_bindings.ko";  // for roles modal


ko.bindingHandlers.permissionIcon = {
    init: function (element) {
        $('<i class="icon"></i> <div class="details"></div>').appendTo(element);
    },
    update: function (element, valueAccessor) {
        var opts = valueAccessor(),
            isEdit = ko.utils.unwrapObservable(opts.edit),
            isView = ko.utils.unwrapObservable(opts.view),
            isManage = ko.utils.unwrapObservable(opts.manage),
            iconEdit = 'fa-solid fa-check',
            iconView = 'fa-solid fa-eye',
            iconManage = 'fa-solid fa-check',
            details = $(element).find('.details'),
            $icon = $(element).find('.icon');

        if (isEdit) {
            $icon.removeClass(iconView).removeClass(iconManage).addClass(iconEdit);
            details.text("");
        } else if (isView) {
            $icon.removeClass(iconEdit).removeClass(iconManage).addClass(iconView);
            details.text(gettext("View Only"));
        } else if (isManage) {
            $icon.removeClass(iconEdit).removeClass(iconView).addClass(iconManage);
            details.text("");
        } else {
            $icon.removeClass(iconEdit).removeClass(iconView).removeClass(iconManage);
            details.text("");
        }
    },
};

ko.bindingHandlers.linkChecked = {
    // Makes sure that the value accessor is set to true if the checked
    // observable is true.
    update: function (element, valueAccessor, allBindings) {
        var checkedVal = ko.utils.unwrapObservable(allBindings.get('checked'));
        if (checkedVal) {
            valueAccessor()(checkedVal);
        }
    },
};

$(function () {
    var url = initialPageData.reverse;

    var $userRolesTable = $('#user-roles-table');
    let $linkedRolesModal = $('#modal_linked_roles');
    const $infoBar = $('#infobar');

    userRoles.initUserRoles($userRolesTable, $linkedRolesModal, $infoBar, {
        userRoles: initialPageData.get("user_roles"),
        deleteUrl: url("delete_user_role"),
        allowEdit: initialPageData.get("can_edit_roles"),
    });
});
