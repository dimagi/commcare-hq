hqDefine("app_manager/js/settings/translations", function () {
    var multimediaTranslationsModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, ['baseUrl']);
        var self = {};

        self.file = ko.observable();
        self.lang = ko.observable();
        self.url = ko.computed(function () {
            return options.baseUrl + "?lang=" + self.lang();
        });

        return self;
    };

    $(function () {
        // Bulk CommCare translations
        var $commcareForm = $("#bulk_ui_translation_upload_form");
        if ($commcareForm.length) {
            $commcareForm.koApplyBindings({
                file: ko.observable(),
            });
        }

        // Bulk application translations
        var $appForm = $("#bulk_app_translation_upload_form");
        if ($appForm.length) {
            $appForm.koApplyBindings({
                file: ko.observable(),
            });
        }

        // Bulk multimedia translations
        var $multimediaPanel = $("#bulk-multimedia-translations");
        if ($multimediaPanel.length) {
            $multimediaPanel.koApplyBindings(multimediaTranslationsModel({
                baseUrl: $multimediaPanel.find("#download_link").attr("href"),
            }));

            $multimediaPanel.find("#bulk_app_multimedia_upload_form").html("<div class='alert alert-info'>Upload is not yet supported.</div>");
        }
    });
});
