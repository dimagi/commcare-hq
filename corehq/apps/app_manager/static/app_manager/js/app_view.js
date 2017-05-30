/* Behavior for app_view.html, regardless of document type (i.e., applies to both normal and remote apps) */
hqDefine("app_manager/js/app_view.js", function() {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
            reverse = hqImport("hqwebapp/js/urllib.js").reverse;

        // Settings
        var $settingsContainer = $('#commcare-settings');
        if ($settingsContainer.length) {
            var CommcareSettings = hqImport('app_manager/js/commcaresettings.js').CommcareSettings;
            $settingsContainer.koApplyBindings(new CommcareSettings(initial_page_data("app_view_options")));
        }

        // Languages
        var $languagesContainer = $("#supported-languages");
        if ($languagesContainer.length) {
            var SupportedLanguages = hqImport('app_manager/js/supported-languages.js').SupportedLanguages;
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
                domain_names: initial_page_data("domain_names"),
            });
        }

        // Multimedia analytics
        $(document).on("click", '#download_zip', function() {
            ga_track_event('App Builder', 'Download Multimedia');
        });
        $(document).on("click", '#open_checker', function() {
            ga_track_event('App Builder', 'Manage Multimedia');
        });

        // Multimedia content
        var MultimediaTab = function () {
            var self = {};
            self.load_state = ko.observable(null);
            self.multimedia_page_html = ko.observable('');
            self.load_if_necessary = function () {
                if (!self.load_state() || self.load_state() === 'error') {
                    self.load_state('loading');
                    $.ajax({
                        url: hqImport("hqwebapp/js/urllib.js").reverse("app_multimedia_ajax"),
                        success: function(content) {
                            self.load_state('loaded');
                            self.multimedia_page_html(content);
                        },
                        error: function() {
                            alert(gettext('Oops, there was a problem loading this section. Please try again.'));
                            self.load_state('error');
                        },
                    });
                }
            };
            return self;
        };
        if ($('#multimedia-tab').length) {
            var multimediaTab = new MultimediaTab();
            $("#multimedia-tab").koApplyBindings(multimediaTab);
            var selector = COMMCAREHQ.toggleEnabled('APP_MANAGER_V2') ? '[href="#multimedia-tab"]' : '#demand-multimedia';
            $(selector).on('shown.bs.tab', function () {
                if (multimediaTab.load_state() === null) {
                    multimediaTab.load_if_necessary();
                }
            });
        }
    });
});
