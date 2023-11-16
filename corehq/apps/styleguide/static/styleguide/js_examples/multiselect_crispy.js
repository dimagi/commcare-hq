$(function () {
    let teamListener = function() {
        console.log("Triggered willSelectAllListener");
    };

    $(function () {
        var multiselect_utils = hqImport('hqwebapp/js/multiselect_utils');
        multiselect_utils.createFullMultiselectWidget('id_team', {
            selectableHeaderTitle: gettext("Benched"),
            selectedHeaderTitle: gettext("Playing"),
            searchItemTitle: gettext("Search Team..."),
            disableModifyAllActions: false,
            willSelectAllListener: teamListener,
        });
    });
});
