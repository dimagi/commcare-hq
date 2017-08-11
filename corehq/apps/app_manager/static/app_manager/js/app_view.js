/* globals COMMCAREHQ */
/* Behavior for app_view.html, regardless of document type (i.e., applies to both normal and remote apps) */
hqDefine("app_manager/js/app_view.js", function() {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
            reverse = hqImport("hqwebapp/js/initial_page_data.js").reverse;

        // Settings
        var $settingsContainer = $('#commcare-settings');
        if ($settingsContainer.length) {
            var CommcareSettings = hqImport('app_manager/js/settings/commcare_settings.js').CommcareSettings;
            $settingsContainer.koApplyBindings(new CommcareSettings(initial_page_data("app_view_options")));
        }

        // Languages
        var $languagesContainer = $("#supported-languages");
        if ($languagesContainer.length) {
            var SupportedLanguages = hqImport('app_manager/js/supported_languages.js').SupportedLanguages;
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
                        url: hqImport("hqwebapp/js/initial_page_data.js").reverse("app_multimedia_ajax"),
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
            var selector = COMMCAREHQ.toggleEnabled('APP_MANAGER_V1') ? '#demand-multimedia' : '[href="#multimedia-tab"]';
            $(selector).on('shown.bs.tab', function () {
                if (multimediaTab.load_state() === null) {
                    multimediaTab.load_if_necessary();
                }
            });
        }

        // Releases content (v1 only)
        if (COMMCAREHQ.toggleEnabled('APP_MANAGER_V1')) {
            var state = "",
                $main = $("#releases"),
                $loading = $main.find(".hq-loading").remove(),
                $loadingError = $main.find(".hq-loading-error").remove();

            $('#demand-releases').on('shown.bs.tab', function () {
                if (state === "loading" || state === "loaded") {
                    return;
                }
                state = "loading";

                // If the content takes a noticeable amount of time to load, show a spinner
                var showSpinner = true;
                _.delay(function() {
                    if (showSpinner) {
                        $main.html($loading.html());
                    }
                }, 100);

                // Load the content
                $.ajax({
                    url: hqImport("hqwebapp/js/initial_page_data.js").reverse('release_manager_ajax') + "?limit=" + initial_page_data("fetch_limit"),
                    success: function(content) {
                        state = "loaded";
                        showSpinner = false;
                        $main.html(content);
                        COMMCAREHQ.initBlock($main);
                        analytics.workflow('Visited the Release Manager');

                        // Main releases/versions tab
                        var o = {
                            currentAppVersion: initial_page_data("app_version") || -1,
                            recipient_contacts: initial_page_data("sms_contacts"),
                            download_modal_id: '#download-zip-modal',
                            fetchLimit: initial_page_data("fetch_limit"),
                        };
                        var el = $('#releases-table');
                        var ReleasesMain = hqImport('app_manager/js/releases/releases.js').ReleasesMain;
                        var releasesMain = new ReleasesMain(o);
                        _.defer(function(){ releasesMain.getMoreSavedApps(false); });
                        el.koApplyBindings(releasesMain);

                        // Build profiles
                        $profileManager = $("#profiles-tab");
                        if ($profileManager.length) {
                            var app_langs = initial_page_data('langs');
                            var app_profiles = initial_page_data('build_profiles');
                            var enable_practice_users = initial_page_data('enable_practice_users');
                            var practice_users = initial_page_data('practice_users');
                            var ProfileManager = hqImport('app_manager/js/releases/language_profiles.js').ProfileManager;
                            $profileManager.koApplyBindings(new ProfileManager(app_profiles, app_langs, enable_practice_users, practice_users));
                        }

                        // App diff
                        var appDiff = hqImport('app_manager/js/releases/app_diff.js').init('#app-diff-modal .modal-body');
                        $('#recent-changes-btn').on('click', function (e) {
                            appDiff.renderDiff(initial_page_data("app_id"), initial_page_data("latest_build_id"));
                        });
                    },
                    error: function() {
                        state = "error";
                        showSpinner = false;
                        $main.html($loadingError.html());
                    },
                });
            });
        }
    });
});
