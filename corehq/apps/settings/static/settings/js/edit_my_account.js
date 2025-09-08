import "commcarehq";
import $ from "jquery";
import "select2/dist/js/select2.full.min";

$(function () {
    $('#id_language').select2();

    $('form[name="user_information"]').on("change", null, null, function () {
        $(":submit").prop("disabled", false);
    }).on("input", null, null, function () {
        $(":submit").prop("disabled", false);
    });
});
