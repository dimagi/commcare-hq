hqDefine('case_importer/js/excel_fields.js', function () {
    function ExcelFieldRows(excelFields, caseFieldSpecs) {
        var self = {
            excelFields: excelFields,
            caseFieldSpecs: caseFieldSpecs,
        };
        self.mappingRows = ko.observableArray();
        // initialize mappingRows with one row per excelField
        _.each(excelFields, function (excelField) {
            var row = {
                excelField: ko.observable(excelField),
                selectedCaseField: ko.observable(null),
                customCaseField: ko.observable(''),
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
        });
//        setInterval(function () {
//            var row = self.mappingRows()[0];
//            console.log(row.isCustom(), row.caseFieldSpec());
//        }, 1000);
        return self;
    }
    return {ExcelFieldRows: ExcelFieldRows};
});
