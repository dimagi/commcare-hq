/* eslint-env mocha */

describe('ExportColumn', function () {
    var selectedColumn,
        advancedColumn,
        deletedColumn,
        table,
        instance,
        viewModels = hqImport('export/js/models');

    beforeEach(function () {
        selectedColumn = {
            selected: true,
            is_advanced: true,
            is_deleted: true,
            deid_transform: null,
        };
        advancedColumn = {
            selected: false,
            is_advanced: true,
            is_deleted: false,
            deid_transform: null,
        };
        deletedColumn = {
            selected: false,
            is_advanced: false,
            is_deleted: true,
            deid_transform: null,
        };
        table = {
            name: 'table',
            selected: true,
            columns: [
                selectedColumn,
                advancedColumn,
                deletedColumn,
            ],
        };
        instance = new viewModels.ExportInstance({
            name: 'instance',
            is_deidentified: false,
            export_format: 'csv',
            tables: [table],
        });
    });

    it('should properly show visible columns', function () {
        var columns,
            table = instance.tables()[0];


        columns = _.filter(table.columns(), function (c) { return c.isVisible(table); });

        // Only the selected one should be visible
        assert.equal(columns.length, 1);
        assert.isTrue(columns[0].selected());

        table.toggleShowAdvanced(table);
        columns = _.filter(table.columns(), function (c) { return c.isVisible(table); });

        // Only the selected one and the advanced one should be visible
        assert.equal(columns.length, 2);

        instance.toggleShowDeleted(table);
        columns = _.filter(table.columns(), function (c) { return c.isVisible(table); });

        // All the columns should be visible
        assert.equal(columns.length, 3);
    });

});
