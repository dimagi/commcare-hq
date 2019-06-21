hqDefine("hqwebapp/js/bulk_upload_file", [
    "jquery",
    "knockout",
], function (
    $,
    ko
) {
    $(function () {
        "use strict";
        var $form = $("#bulk_upload_form");
        if ($form.length) {
            $form.koApplyBindings({
                file: ko.observable(),
            });
        }
    });

    return 1;
});
