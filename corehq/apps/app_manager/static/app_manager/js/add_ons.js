import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqMain from "hqwebapp/js/bootstrap3/main";

function EditAddOns(addOns, layout, saveUrl) {
    const self = this;

    self.addOns = {};
    Object.entries(addOns).forEach(([slug, enabled]) => {
        self.addOns[slug] = ko.observable(enabled);
    });

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
                Object.entries(self.addOns).map(
                    ([slug, observable]) => [slug, observable() ? 'on' : '']
                )
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

    Object.values(self.addOns).forEach(observable => {
        observable.subscribe(() => {
            self.saveButton.fire('change');
        });
    });

    self.toggleSection = function (section) {
        const newCollapseState = !section.collapse();
        section.collapse(newCollapseState);
        const key = self.getStorageKey(section.slug);
        localStorage.setItem(key, newCollapseState.toString());
    };

    self.enableAll = function () {
        Object.entries(self.addOns).forEach(([slug, observable]) => {
            observable(true);
        });
        self.sections.forEach((section) => {
            section.collapse(false);
        });
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
