hqDefine("app_manager/js/settings/translations", [
    "jquery",
    "knockout",
    "hqwebapp/js/assert_properties",
], function (
    $,
    ko,
    assertProperties,
) {
    var appTranslationsModel = function (options) {
        assertProperties.assertRequired(options, ['baseUrl', 'format', 'lang', 'skipBlacklisted']);
        var self = {};

        self.file = ko.observable();
        self.format = ko.observable(options.format);
        self.lang = ko.observable(options.lang);
        self.skipBlacklisted = ko.observable(options.skipBlacklisted);
        self.url = ko.computed(function () {
            return options.baseUrl + "?lang=" + self.lang() + "&skipbl=" + self.skipBlacklisted() + "&format=" + self.format();
        });

        self.disableDownload = ko.computed(function () {
            return self.format() === "single" && !self.lang();
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
        var $translationsPanel = $("#bulk-application-translations");
        if ($translationsPanel.length) {
            $translationsPanel.koApplyBindings(appTranslationsModel({
                baseUrl: $translationsPanel.find("#download_link").attr("href"),
                format: $translationsPanel.find("#sheet_format").val(),
                lang: $translationsPanel.find("select").val() || '',
                skipBlacklisted: $translationsPanel.find("#skip_blacklisted").val(),
            }));
        }
    });
});
