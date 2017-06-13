hqDefine("app_manager/js/labs.js", function() {
    function EditLabs(labs, saveUrl) {
        var self = this;

        self.labs = ko.observableArray(_.values(labs));
        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: gettext("You have unsaved changes."),
            save: function () {
                // Send server map of slug => enabled
                var data = _.mapObject(_.indexBy(self.labs(), 'slug'), function(lab) { return lab.enabled ? 'on' : ''; });
                self.saveButton.ajax({
                    url: saveUrl,
                    type: 'post',
                    data: data,
                    error: function () {
                        throw gettext("There was an error saving.");
                    },
                });
            },
        });
        self.update = function(lab) {
            self.saveButton.fire('change');
        };
    }

    $(function() {
        $("#labs").koApplyBindings(new EditLabs(
            hqImport("hqwebapp/js/initial_page_data.js").get("labs"),
            hqImport("hqwebapp/js/urllib.js").reverse("edit_labs"),
        ));
    });
});
