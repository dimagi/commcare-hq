import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqMain from "hqwebapp/js/bootstrap3/main";
import sectionChanger from "app_manager/js/section_changer";

class EditAddOns {
    constructor(addOns, layout, saveUrl) {
        this.addOns = addOns;
        this.sections = layout.map(s => ({
            ...s,
            collapse: sectionChanger.shouldCollapse("add-ons", s.slug, s.collapse),
        }));
        this.saveButton = hqMain.initSaveButton({
            unsavedMessage: gettext("You have unsaved changes."),
            save: () => {
                // Send server map of slug => enabled
                const data = Object.fromEntries(
                    Object.entries(this.addOns).map(([slug, enabled]) => [slug, enabled ? 'on' : ''])
                );
                this.saveButton.ajax({
                    url: saveUrl,
                    type: 'post',
                    data,
                    error: () => {
                        throw gettext("There was an error saving.");
                    },
                });
            },
        });
    }

    update(addOn, e) {
        this.addOns[addOn.slug] = e.currentTarget.checked;
        this.saveButton.fire('change');
    }
}

$(() => {
    const $addOns = $("#add-ons");
    if ($addOns.length) {
        $addOns.koApplyBindings(new EditAddOns(
            initialPageData.get("add_ons"),
            initialPageData.get("add_ons_layout"),
            initialPageData.reverse("edit_add_ons"),
        ));
        sectionChanger.attachToForm($addOns.find("form"));
    }
});
