hqDefine('case_importer/js/excel_fields', function () {
    function ExcelFieldRows(excelFields, caseFieldSpecs) {
        var self = {
            excelFields: excelFields,
            caseFieldSpecs: caseFieldSpecs,
        };
        self.caseFieldSpecsInMenu = _(caseFieldSpecs).where({show_in_menu: true});

        self.caseFieldsInMenu = _(self.caseFieldSpecsInMenu).pluck('field');
        self.caseFieldSuggestions = _.chain(self.caseFieldSpecs).where({discoverable: true}).pluck('field').value();
        self.mappingRows = ko.observableArray();
        self.removeRow = function (row) {
            self.mappingRows.remove(row);
        };
        self.addRow = function (excelField) {
            var row = {
                excelField: ko.observable(excelField),
                selectedCaseField: ko.observable(null),
                customCaseField: ko.observable(excelField),
                isCustom: ko.observable(false),
            };
            row.selectedCaseFieldOrBlank = ko.computed({
                read: function () {
                    return row.isCustom() ? '' : row.selectedCaseField();
                },
                write: row.selectedCaseField,
            });
            row.customCaseFieldOrBlank = ko.computed({
                read: function () {
                    return row.isCustom() ? row.customCaseField() : '';
                },
                write: row.customCaseField,
            });

            row.caseField = ko.computed(function () {
                if (row.isCustom()) {
                    return row.customCaseField();
                } else {
                    return row.selectedCaseField();
                }
            });

            row.caseFieldSpec = ko.computed(function () {
                return _(caseFieldSpecs).findWhere({field: row.caseField()}) || {};
            });
            row.hasDiscoverableSpecialField = ko.computed(function () {
                return row.caseFieldSpec().description && row.caseFieldSpec().discoverable;
            });
            row.hasNonDiscoverableField = ko.computed(function () {
                return row.caseFieldSpec().description && !row.caseFieldSpec().discoverable;
            });
            row.reset = function () {
                var field = row.excelField();
                field = field && sanitizeCaseField(field);
                row.customCaseField(field);
                if (!field || _(self.caseFieldsInMenu).contains(field)) {
                    row.isCustom(false);
                    row.selectedCaseField(field);
                } else {
                    row.isCustom(true);
                    row.selectedCaseField(null);
                }
            };
            row.reset();
            row.caseFieldSuggestions = ko.computed(function () {
                var field = row.caseField();
                if (!field || _(self.caseFieldSuggestions).contains(field)) {
                    return [];
                }
                var suggestions = _(self.caseFieldSuggestions).map(function (suggestion) {
                    return {
                        // make distance case-insensitive
                        distance: window.Levenshtein.get(field.toLowerCase(), suggestion.toLowerCase()),
                        field: suggestion,
                    };
                }).filter(function (suggestion) {
                    return suggestion.distance < 4;
                });
                return _.chain(suggestions).sortBy('distance').pluck('field').value();
            });

            self.mappingRows.push(row);
        };
        self.autoFill = function () {
            _(self.mappingRows()).each(function (row) {
                row.reset();
            });
        };

        // initialize mappingRows with one row per excelField
        _.each(excelFields, self.addRow);

        return self;
    }
    var sanitizeCaseField = function (original_value) {
        var value = original_value;
        // space to underscore
        value = value.replace(/\s/g, "_");
        // remove other symbols
        value = value.replace(/[^a-zA-Z0-9_\-]/g, "");
        // remove xml from beginning of string. todo: why (36cafb01)?
        value = value.replace(/^xml/i, "");
        return value;
    };
    return {
        ExcelFieldRows: ExcelFieldRows,
        sanitizeCaseField: sanitizeCaseField,
    };
});
