import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqMain from "hqwebapp/js/bootstrap3/main";
import sectionChanger from "app_manager/js/section_changer";

function EditAddOns(addOns, layout, saveUrl) {
    var self = this;

    self.addOns = addOns;
    self.sections = _.map(layout, function (s) {
        return _.extend(s, {
            collapse: sectionChanger.shouldCollapse("add-ons", s.slug, s.collapse),
        });
    });
    self.saveButton = hqMain.initSaveButton({
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
    self.enableAll = function () {
        _.each(self.sections, function (section) {
            sectionChanger.expandSection("add-ons", section.slug);
            _.each(section.add_ons, function (addOn) {
                var $checkbox = $('#check-' + addOn.slug);
                if ($checkbox.length) {
                    $checkbox.prop('checked', true);
                    self.addOns[addOn.slug] = true;
                }
            });
        });

        self.saveButton.fire('change');
    };
}

$(function () {
    var $addOns = $("#add-ons");
    if ($addOns.length) {
        $addOns.koApplyBindings(new EditAddOns(
            initialPageData.get("add_ons"),
            initialPageData.get("add_ons_layout"),
            initialPageData.reverse("edit_add_ons"),
        ));
        sectionChanger.attachToForm($addOns.find("form"));
    }
});
