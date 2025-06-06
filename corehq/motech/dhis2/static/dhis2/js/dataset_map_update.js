import "commcarehq";
import $ from "jquery";
import "hqwebapp/js/bootstrap5/crud_paginated_list_init";
import "hqwebapp/js/bootstrap5/widgets";

function showCompleteDateColumnInput(shouldShow) {
    var label = $('label[for="id_complete_date_column"]').addClass("d-none");
    var element = $('#id_complete_date_column').addClass("d-none");

    if (shouldShow) {
        label.removeClass("d-none");
        element.removeClass("d-none");
    } else {
        label.addClass("d-none");
        element.addClass("d-none");
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
