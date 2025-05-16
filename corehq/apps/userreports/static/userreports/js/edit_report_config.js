import "commcarehq";
import $ from "jquery";
import multiselectUtils from "hqwebapp/js/multiselect_utils";

$(function () {
    multiselectUtils.createFullMultiselectWidget('domain-selector', {
        selectableHeaderTitle: gettext("Linked projects"),
        selectedHeaderTitle: gettext("Projects to copy to"),
        searchItemTitle: gettext("Search projects"),
    });
});
