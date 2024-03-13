hqDefine("app_manager/js/add_ons", function () {
    var sectionChanger = hqImport("app_manager/js/section_changer");

    function EditAddOns(addOns, layout, saveUrl) {
        var self = this;

        self.addOns = addOns;
        self.sections = _.map(layout, function (s) {
            return _.extend(s, {
                collapse: sectionChanger.shouldCollapse("add-ons", s.slug, s.collapse),
            });
        });
        self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
            unsavedMessage: gettext("You have unsaved changes."),
            save: function () {
                // Send server map of slug => enabled
                var data = _.mapObject(self.addOns, function (a) { return a ? 'on' : ''; });
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
        self.update = function (addOn, e) {
            self.addOns[addOn.slug] = e.currentTarget.checked;
            self.saveButton.fire('change');
        };
    }

    $(function () {
        var $addOns = $("#add-ons");
        if ($addOns.length) {
            $addOns.koApplyBindings(new EditAddOns(
                hqImport("hqwebapp/js/initial_page_data").get("add_ons"),
                hqImport("hqwebapp/js/initial_page_data").get("add_ons_layout"),
                hqImport("hqwebapp/js/initial_page_data").reverse("edit_add_ons")
            ));
            sectionChanger.attachToForm($addOns.find("form"));
        }
    });
});
