import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqMain from "hqwebapp/js/bootstrap3/main";

function EditAddOns(addOns, layout, saveUrl) {
    const self = this;

    self.addOns = addOns;

    self.getStorageKey = function (section) {
        return `app-manager-collapse-add-ons-${section}`;
    };

    self.shouldCollapse = function (section, defaultCollapse) {
        const key = self.getStorageKey(section);
        const stored = localStorage.getItem(key);
        return stored !== null ? stored === 'true' : defaultCollapse;
    };

    self.sections = layout.map(s => ({
        ...s,
        collapse: ko.observable(self.shouldCollapse(s.slug, s.collapse)),
    }));

    self.saveButton = hqMain.initSaveButton({
        unsavedMessage: gettext("You have unsaved changes."),
        save: () => {
            // Send server map of slug => enabled
            const data = Object.fromEntries(
                Object.entries(self.addOns).map(([slug, enabled]) => [slug, enabled ? 'on' : ''])
            );
            self.saveButton.ajax({
                url: saveUrl,
                type: 'post',
                data,
                error: () => {
                    throw gettext("There was an error saving.");
                },
            });
        },
    });

    self.update = function (addOn, e) {
        self.addOns[addOn.slug] = e.currentTarget.checked;
        self.saveButton.fire('change');
    };

    self.toggleSection = function (section) {
        const newCollapseState = !section.collapse();
        section.collapse(newCollapseState);
        const key = self.getStorageKey(section.slug);
        localStorage.setItem(key, newCollapseState.toString());
    };
}

$(() => {
    const $addOns = $("#add-ons");
    if ($addOns.length) {
        $addOns.koApplyBindings(new EditAddOns(
            initialPageData.get("add_ons"),
            initialPageData.get("add_ons_layout"),
            initialPageData.reverse("edit_add_ons"),
        ));
    }
});
