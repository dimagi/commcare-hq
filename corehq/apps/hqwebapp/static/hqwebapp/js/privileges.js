hqDefine('hqwebapp/js/privileges', [
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    _,
    initialPageData
) {
    var privilegePresent = function (allPrivileges, privilegeName) {
        return allPrivileges.includes(privilegeName);
    };
    return {
        hasPrivilege: function (privilegeName) {
            return privilegePresent(initialPageData.get('privileges'), privilegeName);
        },
    };
});
