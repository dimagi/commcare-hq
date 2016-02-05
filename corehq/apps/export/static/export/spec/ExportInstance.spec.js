describe('ExportInstance model', function() {

    var basicFormExport;
    beforeEach(function() {
        basicFormExport = _.clone(SampleExportInstances.basic, { saveUrl: 'http://saveurl/' });
        savedFormExport = _.clone(SampleExportInstances.saved, { saveUrl: 'http://saveurl/' });
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
    describe('#isNew', function() {
        var instance;
        beforeEach(function() {
            instance = new Exports.ViewModels.ExportInstance(basicFormExport);
            instanceSaved = new Exports.ViewModels.ExportInstance(savedFormExport);
        });

        it('should correctly determine if instance is new', function() {
            assert.isTrue(instance.isNew());
        });

        it('should correctly determine if instance is new', function() {
            assert.isFalse(instanceSaved.isNew());
        });

    });

    describe('#save', function() {
        var server,
            recordSaveAnalyticsSpy,
            instance;

        beforeEach(function() {
            instance = new Exports.ViewModels.ExportInstance(basicFormExport);
            recordSaveAnalyticsSpy = sinon.spy();
            server = sinon.fakeServer.create();

            sinon.stub(instance, 'recordSaveAnalytics', recordSaveAnalyticsSpy);
            window.ga_track_event = sinon.spy();
        });

        afterEach(function() {
            server.restore();
            instance.recordSaveAnalytics.restore();
            window.ga_track_event = undefined;
        });

        it('Should save a model', function() {
            server.respondWith(
                "POST",
                instance.saveUrl,
                [
                    200,
                    { "Content-Type": "application/json" },
                    '{ "redirect": "http://dummy/"}'
                ]
            );

            assert.equal(instance.saveState(), Exports.Constants.SAVE_STATES.READY);
            instance.save();

            assert.equal(instance.saveState(), Exports.Constants.SAVE_STATES.SAVING);
            server.respond();

            assert.equal(instance.saveState(), Exports.Constants.SAVE_STATES.SUCCESS);
            assert.isTrue(recordSaveAnalyticsSpy.called);
        });

        it('Should crash on saving export', function() {
            server.respondWith(
                "POST",
                instance.saveUrl,
                [
                    500,
                    { "Content-Type": "application/json" },
                    '{ "status": "fail" }'
                ]
            );
            instance.save();

            assert.equal(instance.saveState(), Exports.Constants.SAVE_STATES.SAVING);
            server.respond();

            assert.equal(instance.saveState(), Exports.Constants.SAVE_STATES.ERROR);
            assert.isFalse(recordSaveAnalyticsSpy.called);
        });

    });
});
