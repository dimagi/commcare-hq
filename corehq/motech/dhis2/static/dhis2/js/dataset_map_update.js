hqDefine("dhis2/js/dataset_map_update", [
    "jquery",
    "hqwebapp/js/bootstrap3/crud_paginated_list_init",
    "hqwebapp/js/bootstrap3/widgets",
], function ($) {
    function showCompleteDateColumnInput(shouldShow) {
        var label = $('label[for="id_complete_date_column"]').hide();
        var element = $('#id_complete_date_column').hide();

        if (shouldShow) {
            label.show();
            element.show();
        } else {
            label.hide();
            element.hide();
        }
    }

    function evaluateCompleteDateSelection() {
        var cdoElement = document.getElementById('id_complete_date_option');

        // Second element corresponds to UCR Column,
        // but this is maybe not the best way of determining that
        // this option was selected ...
        if (cdoElement.selectedIndex === 1) {
            showCompleteDateColumnInput(true);
        } else {
            showCompleteDateColumnInput(false);
        }
    }

    evaluateCompleteDateSelection(null);
    var completeDateOptionsElement = document.getElementById('id_complete_date_option');
    completeDateOptionsElement.addEventListener("change", evaluateCompleteDateSelection);
});
