hqDefine("app_manager/js/add_ons.js", function() {
    var sectionChanger = hqImport("app_manager/js/section_changer.js");

    function EditAddOns(addOns, layout, saveUrl) {
        var self = this;

        self.addOnsBySlug = ko.observable(addOns);
        self.sections = _.map(layout, function(s) {
            return _.extend(s, {
                collapse: sectionChanger.shouldCollapse("add-ons", s.slug, s.collapse),
            });
        });
        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: gettext("You have unsaved changes."),
            save: function () {
                // Send server map of slug => enabled
                var data = _.mapObject(self.addOnsBySlug(), function(a) { return a.enabled ? 'on' : ''; });
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
        self.update = function() {
            self.saveButton.fire('change');
        };
    }

    $(function() {
        var $addOns = $("#add-ons");
        $addOns.koApplyBindings(new EditAddOns(
            hqImport("hqwebapp/js/initial_page_data.js").get("add_ons"),
            hqImport("hqwebapp/js/initial_page_data.js").get("add_ons_layout"),
            hqImport("hqwebapp/js/urllib.js").reverse("edit_add_ons"),
        ));
        sectionChanger.attachToForm($addOns.find("form"));
    });
});
