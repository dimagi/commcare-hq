/* Behavior for app_view.html, specific to Application documents (i.e., not remote apps) */
hqDefine("app_manager/js/app_view_application", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");

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

        // Copy app with feature flags
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
    });
});
