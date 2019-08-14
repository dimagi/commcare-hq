hqDefine("app_manager/js/settings/translations", function () {
    var appTranslationsModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, ['baseUrl', 'lang', 'skipBlacklisted']);
        var self = {};

        self.file = ko.observable();
        self.lang = ko.observable(options.lang);
        self.skipBlacklisted = ko.observable(options.skipBlacklisted);
        self.url = ko.computed(function () {
            return options.baseUrl + "?lang=" + self.lang() + "&skipbl=" + self.skipBlacklisted();
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
                lang: $translationsPanel.find("select").val() || '',
                skipBlacklisted: $translationsPanel.find("#skip_blacklisted").val() || '',
            }));
        }
    });
});
