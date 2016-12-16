/* eslint-env mocha */

describe('excel_fields.js', function () {
    var excelfields = hqImport('case_importer/js/excel_fields.js');
    describe('sanitizeCaseField', function () {
        it('should replace spaces with underscores', function () {
            excelfields.sanitizeCaseField('my property name', 'my_property_name');
        });
        it('should leave hyphens untouched', function () {
            excelfields.sanitizeCaseField('my-property-name', 'my-property-name');
        });
        it('should leave underscores untouched', function () {
            excelfields.sanitizeCaseField('my_property_name', 'my_property_name');
        });
        it('should strip leading and trailing whitespace', function () {
            excelfields.sanitizeCaseField('    my_property_name    ', 'my_property_name');
        });
        it('should replace consecutive whitespace with a single underscore', function () {
            excelfields.sanitizeCaseField('my   property  name', 'my_property_name');
        });
    });
});
