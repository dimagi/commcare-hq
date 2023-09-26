hqDefine('app_manager/js/releases/update_prompt', function () {
    function updatePromptModel(form) {
        var self = {};
        var url = form[0].action,
            method = form[0].method;
        self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
            unsavedMessage: gettext("You have unsaved changes to your prompt setting"),
            save: function () {
                self.saveButton.ajax({
                    type: method,
                    url: url,
                    data: $(form[0]).serializeArray(),
                    error: function () {
                        throw gettext("There was an error saving");
                    },
                });
            },
        });
        form.change(function () {
            self.saveButton.fire('change');
        });
        return self;
    }
    $(function () {
        var promptSettingTab = $('#prompt-settings-tab');
        if (promptSettingTab.length) {
            var form = $("#update-manager");

            var updatePrompt = updatePromptModel(form);
            promptSettingTab.koApplyBindings(updatePrompt);
        }

    });
});
