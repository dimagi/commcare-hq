/**
 * Model for sorting configuration on a case list.
 *
 * Sorting config consists of one or more ordered "rows" that
 * each map to a display property column and have
 * sorting-related attributes like direction.
 */
hqDefine("app_manager/js/details/sort_rows", function () {
    var uiElement = hqImport('hqwebapp/js/bootstrap3/ui-element');

    var sortRow = function (params, saveButton) {
        var Utils = hqImport('app_manager/js/details/utils'),
            self = {};
        params = params || {};

        self.selectField = uiElement.select(params.properties).val(typeof params.field !== 'undefined' ? params.field : "");
        Utils.setUpAutocomplete(self.selectField, params.properties);
        self.sortCalculation = ko.observable(typeof params.sortCalculation !== 'undefined' ? params.sortCalculation : "");

        self.showWarning = ko.observable(false);
        self.hasValidPropertyName = function () {
            let name = self.selectField.val();
            // changes here should also be made in
            // corehq.apps.app_manager.helpers.validators.ModuleDetailValidatorMixin._validate_detail_screen_field
            if (new RegExp('^_cc_calculated_(\\d+)$').test(name)) {
                // special case for calculated properties
                return true;
            }
            return Utils.isValidPropertyName(name);
        };
        self.display = ko.observable(typeof params.display !== 'undefined' ? params.display : "");
        self.display.subscribe(function () {
            self.notifyButton();
        });
        self.toTitleCase = Utils.toTitleCase;
        self.selectField.on('change', function () {
            if (!self.hasValidPropertyName()) {
                self.showWarning(true);
            } else {
                self.showWarning(false);
                let display = self.toTitleCase(this.valLabel()).split('(')[0].trim();
                self.display(display);
                self.notifyButton();
            }
        });

        self.type = ko.observable(typeof params.type !== 'undefined' ? params.type : "");
        self.type.subscribe(function () {
            self.notifyButton();
        });
        self.direction = ko.observable(params.direction || "ascending");
        self.blanks = ko.observable(params.blanks || (params.direction === "descending" ? "last" : "first"));
        self.direction.subscribe(function () {
            self.notifyButton();
        });
        self.blanks.subscribe(function () {
            self.notifyButton();
        });
        self.sortCalculation.subscribe(function () {
            self.notifyButton();
        });

        self.notifyButton = function () {
            saveButton.fire('change');
        };

        self.ascendText = ko.computed(function () {
            var type = self.type();
            // This is here for the CACHE_AND_INDEX feature
            if (type === 'plain' || type === 'index') {
                return gettext('Increasing (a, b, c)');
            } else if (type === 'date') {
                return gettext('Increasing (May 1st, May 2nd)');
            } else if (type === 'int') {
                return gettext('Increasing (1, 2, 3)');
            } else if (type === 'double' || type === 'distance') {
                return gettext('Increasing (1.1, 1.2, 1.3)');
            }
        });

        self.descendText = ko.computed(function () {
            var type = self.type();
            if (type === 'plain' || type === 'index') {
                return gettext('Decreasing (c, b, a)');
            } else if (type === 'date') {
                return gettext('Decreasing (May 2nd, May 1st)');
            } else if (type === 'int') {
                return gettext('Decreasing (3, 2, 1)');
            } else if (type === 'double' || type === 'distance') {
                return gettext('Decreasing (1.3, 1.2, 1.1)');
            }
        });

        return self;
    };

    /**
     *
     * @param properties
     * @param saveButton
     * The button that should be activated when something changes
     * @constructor
     */
    var sortRows = function (properties, saveButton) {
        var self = {};
        self.sortRows = ko.observableArray([]);
        self.properties = properties;

        self.addSortRow = function (field, type, direction, blanks, display, notify, sortCalculation) {
            self.sortRows.push(sortRow({
                field: field,
                type: type,
                direction: direction,
                blanks: blanks,
                display: display,
                properties: [...self.properties],  // clone list here to avoid updates from select2 leaking out
                sortCalculation: sortCalculation,
            }, saveButton));
            if (notify) {
                saveButton.fire('change');
            }
        };
        self.removeSortRow = function (row) {
            self.sortRows.remove(row);
            saveButton.fire('change');
        };

        self.rowCount = ko.computed(function () {
            return self.sortRows().length;
        });

        self.showing = ko.computed(function () {
            return self.rowCount() > 0;
        });

        self.updateSortProperties = function (newProperties, changedValues) {
            self.properties = newProperties;

            // update existing sort rows with the new options
            // and re-apply the selected value
            self.sortRows().forEach((row) => {
                let oldSelection = row.selectField.val();
                row.selectField.setOptions(newProperties);
                if (changedValues[oldSelection] !== undefined) {
                    // handle changed values and deletions
                    row.selectField.val(changedValues[oldSelection]);
                } else {
                    row.selectField.val(oldSelection);
                }
                row.selectField.fire("change");
            });
        };

        return self;
    };

    return sortRows;
});
