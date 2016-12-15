hqDefine('case_importer/js/excel_fields.js', function () {
    function ExcelFieldRows(excelFields, caseFieldSpecs) {
        var self = {
            excelFields: excelFields,
            caseFieldSpecs: caseFieldSpecs,
        };
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
                return _(caseFieldSpecs).findWhere({field: row.caseField()});
            });

            self.mappingRows.push(row);
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
