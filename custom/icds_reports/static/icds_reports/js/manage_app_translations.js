hqDefine("icds_reports/js/manage_app_translations", [
    "jquery",
    "hqwebapp/js/widgets_v4",
], function ($) {
    var formManager = {
        action: $("#id_action"),
        update_resource: $("#div_id_update_resource input[name='update_resource']")[0],
        perform_translated_check: $("#id_perform_translated_check")[0],
        lock_translations: $("#id_lock_translations")[0],
        use_version_postfix: $("#div_id_use_version_postfix input[name='use_version_postfix']")[0],
        application: $("#id_app_id"),
        version: $("#id_version"),
        project: $("#id_transifex_project_slug"),
        source_lang: $("#id_source_lang"),
        target_lang: $("#id_target_lang"),
        reset: function () {
            this.action.val("push");
            this.update_resource.checked = false;
            this.perform_translated_check.checked = false;
            this.lock_translations.checked = false;
            $("#div_id_update_resource").hide();
            $("#div_id_perform_translated_check").hide();
            $("#div_id_lock_translations").hide();
            $("#div_id_action").hide();
        },
        getAction: function () { return this.action.val(); },
        getAppName: function () { return this.application.find("option:selected").text(); },
        getVersion: function () { return this.version.val(); },
        shouldUseVersionPostfix: function () { return this.use_version_postfix.checked; },
        shouldUpdateResources: function () { return this.update_resource.checked; },
        getTransifexProject: function () { return this.project.val(); },
        getSourceLang: function () { return this.source_lang.find("option:selected").text(); },
        getTargetLang: function () { return this.target_lang.find("option:selected").text(); },
        shouldLockTranslations: function () { return this.lock_translations.checked; },
        shouldCheckTranslationCompletion: function () { return this.perform_translated_check.checked; },
        createConfirmationMessage: function () {
            var action = formManager.getAction();
            var version =  formManager.getVersion();
            var message = "You want to ";
            if (action === "push") { message = message.concat("push translations on project "); }
            else { message = message.concat("pull translations from project "); }
            message = message.concat(this.getTransifexProject(), ' for application ', this.getAppName());
            if (version === "") { message = message.concat("(current saved app state)"); }
            else { message = message.concat("(version " + version + ")"); }
            message = message.concat(' for language ');
            if (this.target_lang.find("option:selected").val()) {
                message = message.concat(this.getTargetLang(), ". ");
            } else {
                message = message.concat(this.getSourceLang(), ". ");
            }

            if (this.shouldUseVersionPostfix()) {
                message = message.concat("You want to track files according to version");
            } else {
                message = message.concat("You want to track files independent of version");
            }

            if (action === "push") {
                if (this.shouldUpdateResources()) {
                    message = message.concat(" and want to update existing resources on Transifex.");
                } else {
                    message = message.concat(" and want to create new resources on Transifex.");
                }
            }

            if (this.shouldLockTranslations()) {
                message = message.concat(" You want to lock translations that are completed.");
            }

            if (this.shouldCheckTranslationCompletion()) {
                message = message.concat(" You want to check for translation completion before pulling.");
            }

            return (message.concat(" Does that all sound good and you want to proceed?"));
        },
        createDeleteConfirmationMessage: function () {
            return "You want to delete all resources for project " + this.project.val() + ". " +
                   "Beware that this removes all files on Transifex, both source and target langs. " +
                   "We would still check for translations and even if a single resource is not completely translated this request won't be accepted." +
                   " Does that all sound good and you want to proceed?";
        },
    };
    $("#create-tab").click(function () {
        formManager.reset();
    });
    $("#update-tab").click(function () {
        formManager.reset();
        formManager.update_resource.checked = true;
    });
    $("#pull-tab").click(function () {
        formManager.reset();
        formManager.action.val("pull");
        $("#id_perform_translated_check")[0].checked = true;
        $("#div_id_perform_translated_check").show();
        $("#div_id_lock_translations").show();
    });
    $("#advanced-tab").click(function () {
        formManager.reset();
        $("#div_id_update_resource").show();
        $("#div_id_perform_translated_check").show();
        $("#div_id_lock_translations").show();
        $("#div_id_action").show();
    });
    $("#app-translations").submit(function () {
        var action = formManager.action.val();
        if (action === "push" || action === "pull") {
            if (confirm(formManager.createConfirmationMessage()) === false) {
                return false;
            }
        }
        if (action === "delete") {
            if (confirm(formManager.createDeleteConfirmationMessage()) === false) {
                return false;
            }
        }
    });
    $("#create-tab").click();
});