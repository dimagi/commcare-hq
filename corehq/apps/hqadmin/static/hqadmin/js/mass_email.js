import "commcarehq";
import $ from "jquery";

$(function () {
    $('#real_email').click(function (e) {
        if ($(this).prop('checked')) {
            $('#warning_modal').modal('show');
            e.preventDefault();
        }
    });

    $('#accept_mass_email').click(function () {
        $('#real_email').prop('checked', 'checked');
    });
});
