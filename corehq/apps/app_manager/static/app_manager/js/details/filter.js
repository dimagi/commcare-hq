/**
 * Model for the case list filter, which has a button to
 * "Add Filter" when there's no filter, and when clicked
 * shows a textarea for the filter and a button to remove it.
 *
 * @param filterText Initial text of the filter
 * @param saveButton Save button for case list config
 */
hqDefine("app_manager/js/details/filter", function () {
    return function (filterText, saveButton) {
        var self = {};
        self.filterText = ko.observable(typeof filterText === "string" && filterText.length > 0 ? filterText : "");
        self.showing = ko.observable(self.filterText() !== "");

        self.filterText.subscribe(function () {
            saveButton.fire('change');
        });
        self.showing.subscribe(function () {
            saveButton.fire('change');
        });

        self.serialize = function () {
            if (self.showing()) {
                return self.filterText();
            }
            return null;
        };
        return self;
    };
});