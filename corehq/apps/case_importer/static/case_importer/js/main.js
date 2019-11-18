hqDefine("case_importer/js/main", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'case_importer/js/import_history',
    'case_importer/js/excel_fields',
    'hqwebapp/js/widgets',
], function (
    $,
    _,
    initialPageData,
    importHistory,
    excelFieldsModule
) {
    var behaviorForUploadPage = function () {
        var $recentUploads = $('#recent-uploads');
        if (!$recentUploads.length) {
            // We're not on the upload page
            return;
        }

        var recentUploads = importHistory.recentUploadsModel({
            totalItems: initialPageData.get('record_count'),
        });
        $('#recent-uploads').koApplyBindings(recentUploads);
        _.delay(function () {
            recentUploads.goToPage(1);
        });
    };

    var behaviorForExcelMappingPage = function () {
        var excelFields = initialPageData.get('excel_fields');
        var caseFieldSpecs = initialPageData.get('case_field_specs');
        if (!excelFields && !caseFieldSpecs) {
            // We're not on the excel mapping page
            return;
        }

        var excelFieldRows = excelFieldsModule.excelFieldRowsModel(excelFields, caseFieldSpecs);
        $('#excel-field-rows').koApplyBindings(excelFieldRows);

        $('#js-add-mapping').click(function (e) {
            excelFieldRows.addRow();
            e.preventDefault();
        });

        $('.custom_field').on('change, keypress, keydown, keyup', function () {
            var originalValue = $(this).val();
            var value = excelFieldsModule.sanitizeCaseField(originalValue);
            if (value !== originalValue) {
                $(this).val(value);
            }
        });

        $('#field_form').submit(function () {
            $('[disabled]').each(function () {
                $(this).prop('disabled', false);
            });

            return true;
        });

        $('#autofill').click(function () {
            excelFieldRows.autoFill();
        });
    };

    $(function () {
        $('#back_button').click(function () {
            history.back();
            return false;
        });

        $('#back_breadcrumb').click(function (e) {
            e.preventDefault();
            history.back();
            return false;
        });

        behaviorForUploadPage();
        behaviorForExcelMappingPage();
    });
});
