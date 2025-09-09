
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";

var privilegePresent = function (allPrivileges, privilegeName) {
    return allPrivileges.includes(privilegeName);
};
export default {
    hasPrivilege: function (privilegeName) {
        return privilegePresent(initialPageData.get('privileges'), privilegeName);
    },
};
