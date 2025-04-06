import $ from 'jquery';
import multiselectUtils from 'hqwebapp/js/multiselect_utils';

let teamListener = function () {
    console.log("Triggered willSelectAllListener");
};

$(function () {
    multiselectUtils.createFullMultiselectWidget('id_team', {
        selectableHeaderTitle: gettext("Benched"),
        selectedHeaderTitle: gettext("Playing"),
        searchItemTitle: gettext("Search Team..."),
        disableModifyAllActions: false,
        willSelectAllListener: teamListener,
    });
});
