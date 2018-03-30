hqDefine('case_importer/js/excel_fields', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
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
        value = value.replace(/[^a-zA-Z0-9_\-]/g, "");  // eslint-disable-line no-useless-escape
        // remove xml from beginning of string, which would be an invalid xml identifier
        value = value.replace(/^xml/i, "");
        return value;
    };

    $(function() {
        var excelFields = initialPageData.get('excel_fields');
        var caseFieldSpecs = initialPageData.get('case_field_specs');
        var excelFieldRows = ExcelFieldRows(excelFields, caseFieldSpecs);
        $('#excel-field-rows').koApplyBindings(excelFieldRows);

        function autofillProperties() {
            excelFieldRows.autoFill();
        }

        $('#js-add-mapping').click(function(e) {
            excelFieldRows.addRow();
            e.preventDefault();
        });

        $('.custom_field').on('change, keypress, keydown, keyup', function() {
            var original_value = $(this).val();
            var value = sanitizeCaseField(original_value);
            if (value !== original_value) {
                $(this).val(value);
            }
        });

        $('#field_form').submit(function() {
            $('[disabled]').each(function() {
                $(this).prop('disabled', false);
            });

            return true;
        });

        $('#back_button').click(function() {
            history.back();
            return false;
        });

        $('#autofill').click(autofillProperties);

        $('#back_breadcrumb').click(function(e) {
            e.preventDefault();
            history.back();
            return false;
        });
    });

    return { sanitizeCaseField: sanitizeCaseField };
});
