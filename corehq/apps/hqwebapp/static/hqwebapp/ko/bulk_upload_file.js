/* globals ko */
$(function () {
    "use strict";
    if ($("#bulk_upload_form").get(0)) {
        ko.applyBindings(
            {
                file: ko.observable(null)
            },
            $("#bulk_upload_form").get(0)
        );
    }
    if ($("#bulk_app_translation_upload_form").get(0)){
        ko.applyBindings(
            {
                file: ko.observable(null)
            },
            $("#bulk_app_translation_upload_form").get(0)
        )
    }
});
