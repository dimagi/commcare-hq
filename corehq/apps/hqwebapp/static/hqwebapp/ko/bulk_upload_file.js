/* globals ko */
$(function () {
    "use strict";
    var ids = [
        "#bulk_upload_form",
        "#bulk_ui_translation_upload_form",
        "#bulk_app_translation_upload_form"
    ];
    for (var i=0; i < ids.length; i++){
        if ($(ids[i]).get(0)){
            ko.applyBindings(
                {
                    file: ko.observable(null)
                },
                $(ids[i]).get(0)
            );
        }
    }
});
