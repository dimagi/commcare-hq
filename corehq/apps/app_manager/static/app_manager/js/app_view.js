/* globals hqDefine, hqImport */
/* Behavior for app_view.html, regardless of document type (i.e., applies to both normal and remote apps) */
hqDefine("app_manager/js/app_view", function () {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            reverse = hqImport("hqwebapp/js/initial_page_data").reverse;

        // Settings
        var $settingsContainer = $('#commcare-settings');
        if ($settingsContainer.length) {
            var CommcareSettings = hqImport('app_manager/js/settings/commcare_settings').CommcareSettings;
            $settingsContainer.koApplyBindings(new CommcareSettings(initial_page_data("app_view_options")));
        }

        // Languages
        var $languagesContainer = $("#supported-languages");
        if ($languagesContainer.length) {
            var SupportedLanguages = hqImport('app_manager/js/supported_languages').SupportedLanguages;
            $("#supported-languages").koApplyBindings(new SupportedLanguages({
                langs: initial_page_data("langs"),
                saveURL: reverse("edit_app_langs"),
                validate: !initial_page_data("is_remote_app"),
            }));
        }

        // Set up typeahead for domain names when copying app
        var $domainContainer = $("#id_domain");
        if ($domainContainer.length) {
            $domainContainer.koApplyBindings({
                domain_names: [''].concat(initial_page_data("domain_names")),   // prepend with blank so placeholder works
            });
        }

        // Multimedia analytics
        $(document).on("click", '#download_zip', function () {
            hqImport('analytix/js/google').track.event('App Builder', 'Download Multimedia');
        });
        $(document).on("click", '#open_checker', function () {
            hqImport('analytix/js/google').track.event('App Builder', 'Manage Multimedia');
        });

        // Multimedia content
        var multimediaTabModel = function () {
            var self = {};
            self.load_state = ko.observable(null);
            self.multimedia_page_html = ko.observable('');
            self.load_if_necessary = function () {
                if (!self.load_state() || self.load_state() === 'error') {
                    self.load_state('loading');
                    $.ajax({
                        url: hqImport("hqwebapp/js/initial_page_data").reverse("app_multimedia_ajax"),
                        success: function (content) {
                            self.load_state('loaded');
                            self.multimedia_page_html(content);
                        },
                        error: function (data) {
                            if (data.hasOwnProperty('responseJSON')) {
                                alert(data.responseJSON.message);
                            }
                            else {
                                alert(gettext('Oops, there was a problem loading this section. Please try again.'));
                            }
                            self.load_state('error');
                        },
                    });
                }
            };
            return self;
        };
        if ($('#multimedia-tab').length) {
            var multimediaTab = multimediaTabModel(),
                initializeMultimediaTab = function () {
                    if (multimediaTab.load_state() === null) {
                        multimediaTab.load_if_necessary();
                    }
                };
            $("#multimedia-tab").koApplyBindings(multimediaTab);
            if ($('[href="#multimedia-tab"]').parent().hasClass("active")) {
                // Multimedia tab has already been selected
                initializeMultimediaTab();
            }
            $('[href="#multimedia-tab"]').on('shown.bs.tab', function () {
                initializeMultimediaTab();
            });
        }
    });
});
