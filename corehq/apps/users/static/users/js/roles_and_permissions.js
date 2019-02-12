hqDefine("users/js/roles_and_permissions",[
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'users/js/roles',
    'bootstrap', // for bootstrap modal
    'hqwebapp/js/knockout_bindings.ko', // for staticChecked data binding in web_users.html
], function ($, ko, _, initialPageData, userRoles) {

    ko.bindingHandlers.linkChecked = {
        // Makes sure that the value accessor is set to true if the checked
        // observable is true.
        update: function(element, valueAccessor, allBindings) {
            var checkedVal = ko.utils.unwrapObservable(allBindings.get('checked'));
            if (checkedVal) {
                valueAccessor()(checkedVal);
            }
        },
    };

    $(function () {
        var url = initialPageData.reverse;

        var $userRolesTable = $('#user-roles-table');

        userRoles.initUserRoles($userRolesTable, {
            userRoles: initialPageData.get("user_roles"),
            defaultRole: initialPageData.get("default_role"),
            saveUrl: url("post_user_role"),
            deleteUrl: url("delete_user_role"),
            reportOptions: initialPageData.get("report_list"),
            webAppsList: initialPageData.get("web_apps_list"),
            appsList: initialPageData.get("apps_list"),
            allowEdit: initialPageData.get("can_edit_roles"),
            canRestrictAccessByLocation: initialPageData.get("can_restrict_access_by_location"),
            landingPageChoices: initialPageData.get("landing_page_choices"),
        });
        $userRolesTable.show();
    });
});
