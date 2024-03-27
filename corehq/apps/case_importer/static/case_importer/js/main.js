"use strict";
hqDefine("case_importer/js/main", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'case_importer/js/bootstrap3/import_history',
    'case_importer/js/excel_fields',
    'hqwebapp/js/bootstrap3/widgets',
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

        $('input:file').change(function () {
            const fileName = $(this).val();
            if (fileName) {
                $(':submit').enableButton();
            } else {
                $(':submit').disableButtonNoSpinner();
            }
        });
        // enable button in case of "Back" pressed, file chosen
        if ($('input:file').val()) {
            $(':submit').enableButton();
        }
    };

    var behaviorForOptionsPage = function () {
        var $caseType = $('#case_type');
        if (!$caseType.length) {
            // We're not on the Case Options page
            return;
        }

        $('#field_form').submit(function () {
            $('[disabled]').each(function () {
                $(this).prop('disabled', false);
            });

            return true;
        });
    };

    var behaviorForExcelMappingPage = function () {
        var excelFields = initialPageData.get('excel_fields');
        var caseFieldSpecs = initialPageData.get('case_field_specs');
        if (!excelFields && !caseFieldSpecs) {
            // We're not on the excel mapping page
            return;
        }

        $('#field_form').submit(function () {
            $('[disabled]').each(function () {
                $(this).prop('disabled', false);
            });

            return true;
        });

        if (initialPageData.get('is_bulk_import')) {
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
        behaviorForOptionsPage();
        behaviorForExcelMappingPage();
    });
});
