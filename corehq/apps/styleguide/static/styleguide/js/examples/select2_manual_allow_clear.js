import $ from 'jquery';
import 'select2/dist/js/select2.full.min';

$(function () {
    $("#js-manual-select2-clear").select2({
        allowClear: true,
        placeholder: "Select an option...",
    });
});
