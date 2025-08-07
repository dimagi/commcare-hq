import "commcarehq";
import $ from "jquery";
import "hqwebapp/js/base_ace";

$(function () {
    $('[data-toggle="popover"]').popover();
    $(".submit-dropdown-form").click(function (e) {
        e.preventDefault();
        var $form = $("#dropdown-form");
        $form.attr("action", $(this).data("action"));
        $form.submit();
    });
});
