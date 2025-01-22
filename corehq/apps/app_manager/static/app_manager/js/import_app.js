import "commcarehq";
import $ from "jquery";

$(function () {
    $(".historyBack").click(function () {
        history.back();
        return false;
    });
});
