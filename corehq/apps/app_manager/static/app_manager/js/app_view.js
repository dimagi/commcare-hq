/**
  *  Entry point for the app settings page.
  */
hqDefine("app_manager/js/app_view", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/settings/commcare_settings",
    "app_manager/js/supported_languages",
    "analytix/js/google",
    "hqwebapp/js/bootstrap3/widgets",
    "hqwebapp/js/bootstrap3/main",
    "app_manager/js/app_manager",
    "app_manager/js/section_changer",
], function (
    $,
    ko,
    initialPageData,
    commcareSettings,
    supportedLanguages,
    google,
    widgets,
    main,
    appManager,
    sectionChanger,
) {
    $(function () {
        // App name
        $(document).on("inline-edit-save", function (e, data) {
            if (_.has(data.update, '.variable-app_name')) {
                appManager.updatePageTitle(data.update['.variable-app_name']);
                appManager.updateDOM(data.update);
            }
        });

        // Settings
        var $settingsContainer = $('#commcare-settings');
        if ($settingsContainer.length) {
            $settingsContainer.koApplyBindings(new commcareSettings.CommcareSettings(initialPageData.get("app_view_options")));
        }

        // Languages
        var $languagesContainer = $("#supported-languages");
        if ($languagesContainer.length) {
            $("#supported-languages").koApplyBindings(new supportedLanguages.SupportedLanguages({
                langs: initialPageData.get("langs"),
                saveURL: initialPageData.reverse("edit_app_langs"),
                validate: !initialPageData.get("is_remote_app"),
            }));
        }

        var CopyAppViewModel = function () {
            var self = {};
            // Set up typeahead for domain names when copying app
            // prepend with blank so placeholder works
            self.domainNames = [''].concat(initialPageData.get("domain_names"));
            self.linkableDomains = initialPageData.get("linkable_domains");
            self.shouldLimitToLinkedDomains = initialPageData.get("limit_to_linked_domains");

            self.isChecked = ko.observable(false);
            self.shouldEnableLinkedAppOption = ko.observable(true);

            self.domainChanged = function (data, event) {
                if (self.shouldLimitToLinkedDomains) {
                    var selectedDomain = event.currentTarget.options[event.currentTarget.selectedIndex].value;
                    self.shouldEnableLinkedAppOption(self.linkableDomains.includes(selectedDomain));

                    // ensure not checked if linked apps is not allowed
                    if (!self.shouldEnableLinkedAppOption()) {
                        self.isChecked(false);
                    }
                }
            };

            return self;
        };

        var $domainContainer = $("#copy-app-form");
        if ($domainContainer.length) {
            $domainContainer.koApplyBindings(CopyAppViewModel());
        }

        // Multimedia analytics
        $(document).on("click", '#download_zip', function () {
            google.track.event('App Builder', 'Download Multimedia');
        });
        $(document).on("click", '#open_checker', function () {
            google.track.event('App Builder', 'Manage Multimedia');
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
                        url: initialPageData.reverse("app_multimedia_ajax"),
                        success: function (content) {
                            self.load_state('loaded');
                            self.multimedia_page_html(content);
                            widgets.init();
                        },
                        error: function (data) {
                            if (data.hasOwnProperty('responseJSON')) {
                                alert(data.responseJSON.message);
                            } else {
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

        // Custom Assertions
        (function () {
            var $form = $("#custom-assertions-form");
            var $saveContainer = $form.find("#custom-assertions-save-btn");
            var saveButton = main.initSaveButton({
                save: function () {
                    saveButton.ajax({
                        url: $form.attr('action'),
                        data: {
                            custom_assertions: $form.find('input[name="custom_assertions"]').val(),
                        },
                        type: 'POST',
                    });
                },
            });
            $form.on('change', function () {
                saveButton.fire('change');
            });
            saveButton.ui.appendTo($saveContainer);
            sectionChanger.attachToForm($saveContainer);
        })();

    });
});
