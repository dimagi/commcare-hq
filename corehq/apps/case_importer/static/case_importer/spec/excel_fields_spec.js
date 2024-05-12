"use strict";
/* eslint-env mocha */
hqDefine("case_importer/spec/excel_fields_spec", [
    'case_importer/js/excel_fields',
], function (
    excelFields
) {
    describe('excel_fields', function () {
        describe('sanitizeCaseField', function () {
            it('should replace spaces with underscores', function () {
                excelFields.sanitizeCaseField('my property name', 'my_property_name');
            });
            it('should leave hyphens untouched', function () {
                excelFields.sanitizeCaseField('my-property-name', 'my-property-name');
            });
            it('should leave underscores untouched', function () {
                excelFields.sanitizeCaseField('my_property_name', 'my_property_name');
            });
            it('should strip leading and trailing whitespace', function () {
                excelFields.sanitizeCaseField('    my_property_name    ', 'my_property_name');
            });
            it('should replace consecutive whitespace with a single underscore', function () {
                excelFields.sanitizeCaseField('my   property  name', 'my_property_name');
            });
        });
    });
});
