import "commcarehq";
import $ from "jquery";
import "hqwebapp/js/bootstrap3/widgets";
import "jquery-ui/ui/widgets/sortable";
import "jquery-ui-built-themes/redmond/jquery-ui.min.css";

$(function () {
    $("#hint_id_recipients").addClass("alert alert-info");
    $("#hint_id_message").addClass("alert alert-info");
    $("#id_message").on('keyup', function () {
        var maxChar = 160,
            currentCount = $(this).val().length,
            message = "";
        var charsRemaining = maxChar - currentCount;
        var $charCount = $("#hint_id_message");
        if (charsRemaining < 0) {
            $charCount.addClass("alert-danger").removeClass('alert-info');
        } else {
            $charCount.removeClass("alert-danger").addClass('alert-info');
        }
        message = currentCount + " character";
        if (currentCount !== 1) {
            message = message + "s";
        }
        message = message + " (" + maxChar + " max)";
        $charCount.text(message);
    });
});
