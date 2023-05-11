hqDefine('hqwebapp/js/privileges', [
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    _,
    initialPageData
) {
    var privilegePresent = function (allPrivileges, privilegeName) {
        var value = allPrivileges.includes(privilegeName);
        if (value === false) {
            throw new Error(
                'Privilege ' + privilegeName + ' not recognized. Must be one of: \n\n' +
                allPrivileges.sort()
            );
        }
        return value;
    };
    return {
        hasPrivilege: function (privilegeName) {
            return privilegePresent(initialPageData.get('privileges'), privilegeName);
        },
    };
});
