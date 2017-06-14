hqDefine("app_manager/js/labs.js", function() {
    var sectionChanger = hqImport("app_manager/js/section_changer.js");

    function EditLabs(labs, layout, saveUrl) {
        var self = this;

        self.labsBySlug = ko.observable(labs);
        self.sections = _.map(layout, function(s) {
            return _.extend(s, {
                collapse: sectionChanger.shouldCollapse("labs", s.slug, s.collapse),
            });
        });
        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: gettext("You have unsaved changes."),
            save: function () {
                // Send server map of slug => enabled
                var data = _.mapObject(self.labsBySlug(), function(lab) { return lab.enabled ? 'on' : ''; });
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
        var $labs = $("#labs");
        $labs.koApplyBindings(new EditLabs(
            hqImport("hqwebapp/js/initial_page_data.js").get("labs"),
            hqImport("hqwebapp/js/initial_page_data.js").get("labs_layout"),
            hqImport("hqwebapp/js/urllib.js").reverse("edit_labs"),
        ));
        sectionChanger.attachToForm($labs.find("form"));
    });
});
