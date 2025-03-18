/* Behavior for app_view.html, regardless of document type (i.e., applies to both normal and remote apps) */
hqDefine("app_manager/js/app_view", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");

        // App name
        $(document).on("inline-edit-save", function (e, data) {
            if (_.has(data.update, '.variable-app_name')) {
                var appManager = hqImport('app_manager/js/app_manager');
                appManager.updatePageTitle(data.update['.variable-app_name']);
                appManager.updateDOM(data.update);
            }
        });

        // Settings
        var $settingsContainer = $('#commcare-settings');
        if ($settingsContainer.length) {
            var CommcareSettings = hqImport('app_manager/js/settings/commcare_settings').CommcareSettings;
            $settingsContainer.koApplyBindings(new CommcareSettings(initialPageData.get("app_view_options")));
        }

        // Languages: Language List
        var $languagesContainer = $("#supported-languages");
        if ($languagesContainer.length) {
            var SupportedLanguages = hqImport('app_manager/js/supported_languages').SupportedLanguages;
            $("#supported-languages").koApplyBindings(new SupportedLanguages({
                langs: initialPageData.get("langs"),
                saveURL: initialPageData.reverse("edit_app_langs"),
                validate: !initialPageData.get("is_remote_app"),
            }));
        }

        // Languages: CommCare Translations
        var $ui = $("#translations_ui");
        if ($ui.length) {
            hqImport("translations/js/translations").makeTranslationUI({
                translations: initialPageData.get("translations"),
                url: initialPageData.reverse("edit_app_ui_translations"),
                suggestion_url: initialPageData.reverse("get_app_ui_translations"),
                lang: initialPageData.get("lang"),
                allow_autofill: initialPageData.get("lang") !== 'en',
                $home: $ui,
            });
        }

        // Actions: Copy Application
        $("#copy-app-form form button").click(function () {
            var $submit = $(this),
                $form = $submit.closest("form"),
                domain = $form.find("#id_domain").val(),
                $modal = $("#copy-toggles");

            if (!isCopyApplicationFormValid($form)) {
                return false;
            }

            if (initialPageData.get("is_superuser")) {
                $submit.disableButton();
                $.ajax({
                    method: "GET",
                    url: initialPageData.reverse("toggle_diff"),
                    data: {
                        domain: domain,
                    },
                    success: function (toggles) {
                        if (toggles.length) {
                            var template = _.template($modal.find("script").html()),
                                $ul = $modal.find("ul").html(""),
                                allSelected = false;
                            $modal.find(".select-all").click(function (e) {
                                allSelected = !allSelected;
                                $(e.currentTarget).text(allSelected ? gettext("Select None") : gettext("Select All"));
                                $ul.find("input:checkbox").prop('checked', allSelected);
                            });
                            _.each(toggles, function (toggle) {
                                $ul.append(template(toggle));
                            });
                            $modal.modal().one("click", ".btn-primary", function () {
                                $(this).disableButton();
                                var slugs = _.map($modal.find(":checked"), function (c) {
                                    return $(c).data("slug");
                                });
                                $form.find("input[name='toggles']").val(slugs.join(","));
                                $form.submit();
                            }).one("hide.bs.modal", function () {
                                $submit.enableButton();
                            });
                        } else {
                            $form.submit();
                        }
                    },
                    error: function () {
                        // If anything goes wrong, just submit the form
                        $form.submit();
                    },
                });
            } else {
                $form.submit();
            }
        });

        /***
         * The function is used to validate the copy application form data before submitting it.
         * It checks the following things:
         *      1. the application name is entered or not
         *      2. valid project/domain is selected or not
         * @param form
         * @returns {boolean}
         */
        var isCopyApplicationFormValid = function (form) {
            var domainDiv  = form.find("#div_id_domain"),
                appNameDiv = form.find("#div_id_name"),
                domain = domainDiv.find("#id_domain"),
                appName = appNameDiv.find("#id_name"),
                errorMessage = '',
                domainNames = initialPageData.get("domain_names");

            appNameDiv.removeClass('has-error');
            domainDiv.find('.help-block').remove();

            domainDiv.removeClass('has-error');
            appNameDiv.find('.help-block').remove();

            // If application name is not entered
            if (!appName.val().trim()) {
                appNameDiv.addClass('has-error');
                errorMessage = gettext('Application name is required');
                appName.after($("<span class=\"help-block\"></span>").text(errorMessage));
            }

            // If project/domain is not selected or invalid domain is selected
            if (domainNames.indexOf(domain.val()) === -1) {
                if (!domain.val()) {
                    errorMessage = gettext('Project name is required');
                } else if (!initialPageData.get('is_superuser')) {
                    // Non-superusers can only copy to their own domains
                    errorMessage = gettext('Invalid Project Selected');
                }

                if (errorMessage) {
                    domainDiv.addClass('has-error');
                    domain.after($("<span class=\"help-block\"></span>").text(errorMessage));
                }
            }

            return !errorMessage;
        };

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
                        url: initialPageData.reverse("app_multimedia_ajax"),
                        success: function (content) {
                            self.load_state('loaded');
                            self.multimedia_page_html(content);
                            hqImport("hqwebapp/js/bootstrap3/widgets").init();
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
            var saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
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
            hqImport("app_manager/js/section_changer").attachToForm($saveContainer);
        })();

    });
});
