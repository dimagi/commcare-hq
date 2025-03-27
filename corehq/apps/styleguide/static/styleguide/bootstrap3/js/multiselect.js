import $ from 'jquery';
import multiselectUtils from "hqwebapp/js/multiselect_utils";

let listener = function () {
    console.log("Triggered willSelectAllListener");
};

$(function () {
    multiselectUtils.createFullMultiselectWidget('example-multiselect', {
        selectableHeaderTitle: gettext("Available Letters"),
        selectedHeaderTitle: gettext("Letters Selected"),
        searchItemTitle: gettext("Search Letters..."),
        disableModifyAllActions: false,
        willSelectAllListener: listener,
    });
});
