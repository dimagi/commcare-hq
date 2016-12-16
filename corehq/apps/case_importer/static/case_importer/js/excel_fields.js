hqDefine('case_importer/js/excel_fields.js', function () {
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
                    return {distance: Levenshtein.get(field, suggestion), field: suggestion};
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

//        setInterval(function () {
//            var row = self.mappingRows()[0];
//            console.log(row.isCustom(), row.caseFieldSpec());
//        }, 1000);
        return self;
    }
    return {ExcelFieldRows: ExcelFieldRows};
});
