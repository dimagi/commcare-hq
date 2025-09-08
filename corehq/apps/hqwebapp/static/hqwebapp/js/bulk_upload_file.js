import "commcarehq";
import $ from "jquery";
import ko from "knockout";

$(function () {
    var $form = $("#bulk_upload_form");
    if ($form.length) {
        $form.koApplyBindings({
            file: ko.observable(),
        });
    }
});

export default 1;
