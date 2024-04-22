hqDefine("users/js/roles_and_permissions",[
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'users/js/roles',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // for roles modal
], function ($, ko, _, initialPageData, userRoles) {

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
            nonAdminRoles: initialPageData.get("non_admin_roles"),
            defaultRole: initialPageData.get("default_role"),
            saveUrl: url("post_user_role"),
            deleteUrl: url("delete_user_role"),
            reportOptions: initialPageData.get("report_list"),
            tableauOptions: initialPageData.get("tableau_list"),
            allowEdit: initialPageData.get("can_edit_roles"),
            canRestrictAccessByLocation: initialPageData.get("can_restrict_access_by_location"),
            landingPageChoices: initialPageData.get("landing_page_choices"),
            webAppsChoices: initialPageData.get("web_apps_choices"),
            attendanceTrackingPrivilege: initialPageData.get("attendance_tracking_privilege"),
            DataFileDownloadEnabled: initialPageData.get("data_file_download_enabled"),
            ExportOwnershipEnabled: initialPageData.get("export_ownership_enabled"),
            dataRegistryChoices: initialPageData.get("data_registry_choices"),
            canEditLinkedData: initialPageData.get("can_edit_linked_data"),
        });
    });
});
