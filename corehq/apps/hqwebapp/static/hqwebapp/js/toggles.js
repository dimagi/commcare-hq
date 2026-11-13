
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";

var genericToggleEnabled = function (allToggles, toggleName) {
    var value = allToggles[toggleName];
    if (typeof value === 'undefined') {
        throw new Error(
            'Toggle ' + toggleName + ' not recognized. Must be one of: \n\n' +
            _.sortBy(_.keys(allToggles)).join("\n"),
        );
    }
    return value;
};
export default {
    toggleEnabled: function (toggleName) {
        return genericToggleEnabled(initialPageData.get('toggles_dict'), toggleName);
    },
    previewEnabled: function (toggleName) {
        return genericToggleEnabled(initialPageData.get('previews_dict'), toggleName);
    },
};
