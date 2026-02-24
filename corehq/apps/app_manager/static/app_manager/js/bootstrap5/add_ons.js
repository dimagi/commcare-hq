import $ from "jquery";
import ko from "knockout";
import { Collapse } from "bootstrap5";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqMain from "hqwebapp/js/bootstrap5/main";

function EditAddOns(addOns, layout, saveUrl) {
    const self = this;

    self.addOns = {};
    Object.entries(addOns).forEach(([slug, enabled]) => {
        self.addOns[slug] = ko.observable(enabled);
    });

    self.sections = layout.map(s => ({
        ...s,
    }));

    self.saveButton = hqMain.initSaveButton({
        unsavedMessage: gettext("You have unsaved changes."),
        save: () => {
            // Send server map of slug => enabled
            const data = Object.fromEntries(
                Object.entries(self.addOns).map(
                    ([slug, observable]) => [slug, observable() ? 'on' : ''],
                ),
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

    self.enableAll = function () {
        Object.entries(self.addOns).forEach(([_slug, observable]) => {
            observable(true);
        });
        self.sections.forEach((section) => {
            const $collapseEl = $('#collapse-' + section.slug);
            if ($collapseEl.length) {
                Collapse.getOrCreateInstance($collapseEl).show();
            }
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
