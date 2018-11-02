/* Behavior for app_view.html, specific to Application documents (i.e., not remote apps) */
hqDefine("app_manager/js/app_view_application", function () {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            reverse = hqImport("hqwebapp/js/initial_page_data").reverse;

        // Languages: CommCare Translations
        var $translation_ui = $("#translations_ui");
        if ($translation_ui.length) {
            hqImport("translations/js/translations").makeTranslationUI({
                translations: initial_page_data("translations"),
                url: reverse("edit_app_ui_translations"),
                suggestion_url: reverse("get_app_ui_translations"),
                lang: initial_page_data("lang"),
                allow_autofill: initial_page_data("lang") !== 'en',
                $home: $translation_ui,
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

            if (initial_page_data("is_superuser")) {
                $submit.disableButton();
                $.ajax({
                    method: "GET",
                    url: reverse("toggle_diff"),
                    data: {
                        domain: domain,
                    },
                    success: function (toggles) {
                        if (toggles.length) {
                            var template = _.template($modal.find("script").html()),
                                $ul = $modal.find("ul").html(""),
                                $selectAll = $(template({
                                    slug: "",
                                    label: gettext("<span class='label label-default'>" + gettext("Select All") +
                                    "</span>"),
                                }));
                            $selectAll.find("input:checkbox").change(function () {
                                $ul.find("input:checkbox").prop('checked', $(this).prop('checked'));
                            });
                            $ul.append($selectAll);
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
                error = false,
                domainNames = initial_page_data("domain_names");

            appNameDiv.removeClass('has-error');
            domainDiv.find('.help-block').remove();

            domainDiv.removeClass('has-error');
            appNameDiv.find('.help-block').remove();

            //if application name is not entered
            if (!appName.val().trim()) {
                appNameDiv.addClass('has-error');
                error = true;
                var appErrorMessage = gettext('Application name is required');

                appName.after($("<span class=\"help-block\"></span>").text(appErrorMessage));
            }

            //if project/domain is not selected or invalid domain is selected
            if (domainNames.indexOf(domain.val()) === -1) {

                domainDiv.addClass('has-error');
                error = true;
                var domainErrorMessage = gettext('Invalid Project Selected');

                if (!domain.val()) {
                    domainErrorMessage = gettext('Project name is required');
                }

                domain.after($("<span class=\"help-block\"></span>").text(domainErrorMessage));
            }

            return !error;
        };
            

    });
});
