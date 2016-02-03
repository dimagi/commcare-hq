describe('ExportInstance model', function() {

    var basicFormExport;
    beforeEach(function() {
        basicFormExport = _.clone(SampleExportInstances.basic);
    });

    it('Should create an instance from JSON', function() {
        var instance = new Exports.ViewModels.ExportInstance(basicFormExport);

        assert.equal(instance.tables().length, 1);

        var table = instance.tables()[0];
        assert.equal(table.columns().length, 2);

        _.each(table.columns(), function(column) {
            assert.ok(column.item);
            assert.isTrue(column instanceof Exports.ViewModels.ExportColumn);
            assert.isDefined(column.show());
            assert.isDefined(column.selected());
            assert.isDefined(column.label());

            var item = column.item;
            assert.isTrue(item instanceof Exports.ViewModels.ExportItem);
            assert.isDefined(item.label);
            assert.isDefined(item.path);
            assert.isDefined(item.tag);
        });
    });

    it('Should serialize an instance into JS object', function() {
        var instance = new Exports.ViewModels.ExportInstance(basicFormExport);
        var obj = instance.toJS();
        assert.equal(obj.tables.length, 1);

        var table = obj.tables[0];
        assert.equal(table.columns.length, 2);

        _.each(table.columns, function(column) {
            assert.ok(column.item);
            assert.isFalse(column instanceof Exports.ViewModels.ExportColumn);
            assert.isDefined(column.show);
            assert.isDefined(column.selected);
            assert.isDefined(column.label);

            var item = column.item;
            assert.isFalse(item instanceof Exports.ViewModels.ExportItem);
            assert.isDefined(item.label);
            assert.isDefined(item.path);
            assert.isDefined(item.tag);
        });

    });
});
