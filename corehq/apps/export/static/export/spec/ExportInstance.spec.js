/* eslint-env mocha */
hqDefine("export/spec/ExportInstance.spec", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'export/js/const',
    'export/js/models',
    'export/spec/data/export_instances',
], function (
    $,
    _,
    initialPageData,
    constants,
    viewModels,
    SampleExportInstances
) {
    describe('ExportInstance model', function () {
        var basicFormExport, savedFormExport;
        initialPageData.registerUrl(
            "build_schema", "/a/---/data/export/build_full_schema/"
        );
        beforeEach(function () {
            basicFormExport = _.clone(SampleExportInstances.basic, { saveUrl: 'http://saveurl/' });
            savedFormExport = _.clone(SampleExportInstances.saved, { saveUrl: 'http://saveurl/' });
        });

        it('Should create an instance from JSON', function () {
            var instance = new viewModels.ExportInstance(basicFormExport);

            assert.equal(instance.tables().length, 1);

            var table = instance.tables()[0];
            assert.equal(table.columns().length, 2);

            _.each(table.columns(), function (column) {
                assert.ok(column.item);
                assert.isTrue(column instanceof viewModels.ExportColumn);
                assert.isDefined(column.show());
                assert.isDefined(column.selected());
                assert.isDefined(column.label());

                var item = column.item;
                assert.isTrue(item instanceof viewModels.ExportItem);
                assert.isDefined(item.label);
                assert.isDefined(item.path);
                assert.isDefined(item.tag);
            });
        });

        it('Should serialize an instance into JS object', function () {
            var instance = new viewModels.ExportInstance(basicFormExport);
            var obj = instance.toJS();
            assert.equal(obj.tables.length, 1);

            var table = obj.tables[0];
            assert.equal(table.columns.length, 2);

            _.each(table.columns, function (column) {
                assert.ok(column.item);
                assert.isFalse(column instanceof viewModels.ExportColumn);
                assert.isDefined(column.show);
                assert.isDefined(column.selected);
                assert.isDefined(column.label);

                var item = column.item;
                assert.isFalse(item instanceof viewModels.ExportItem);
                assert.isDefined(item.label);
                assert.isDefined(item.path);
                assert.isDefined(item.tag);
            });
        });
        describe('#isNew', function () {
            var instance, instanceSaved;
            beforeEach(function () {
                instance = new viewModels.ExportInstance(basicFormExport);
                instanceSaved = new viewModels.ExportInstance(savedFormExport);
            });

            it('should correctly determine if instance is new', function () {
                assert.isTrue(instance.isNew());
            });

            it('should correctly determine if instance is new', function () {
                assert.isFalse(instanceSaved.isNew());
            });

        });

        describe('#onBeginSchemaBuild', function () {
            var instance;
            beforeEach(function () {
                instance = new viewModels.ExportInstance(basicFormExport);
                sinon.spy($, "ajax");
            });

            afterEach(function () {
                $.ajax.restore();
            });

            it('should trigger build', function () {
                instance.onBeginSchemaBuild(instance, {});

                assert.equal(instance.buildSchemaProgress(), 0);
                assert.isTrue(instance.showBuildSchemaProgressBar());
                assert.isTrue($.ajax.called);
            });

        });

        describe('#checkBuildSchemaProgress', function () {
            var instance,
                requests,
                clock,
                xhr;
            beforeEach(function () {
                requests = [];
                instance = new viewModels.ExportInstance(basicFormExport);
                clock = sinon.useFakeTimers();
                xhr = sinon.useFakeXMLHttpRequest();
                xhr.onCreate = function (xhr) {
                    requests.push(xhr);
                };
            });

            afterEach(function () {
                xhr.restore();
                clock.restore();
            });

            it('successfully check for pending build', function () {
                var successSpy = sinon.spy(),
                    response = {
                        success: false,
                        failed: false,
                        not_started: false,
                        progress: {
                            percent: 50,
                            current: 50,
                            total: 100,
                        },
                    },
                    successResponse = {
                        success: true,
                        failed: false,
                        progress: {},
                    };
                instance.checkBuildSchemaProgress('123', successSpy, sinon.spy());

                assert.equal(requests.length, 1);
                // Respond with pending build
                requests[0].respond(
                    200,
                    { 'Content-Type': 'application/json' },
                    JSON.stringify(response)
                );

                // Should not have queued up a new request yet
                assert.equal(requests.length, 1);
                assert.equal(instance.buildSchemaProgress(), 50);

                // Fast forward time, should trigger another request
                clock.tick(2001);
                assert.equal(requests.length, 2);
                requests[1].respond(
                    200,
                    { 'Content-Type': 'application/json' },
                    JSON.stringify(successResponse)
                );

                assert.isTrue(successSpy.called);
                assert.equal(instance.buildSchemaProgress(), 100);
                assert.isFalse(instance.showBuildSchemaProgressBar());
            });
        });

        describe('#save', function () {
            var server,
                recordSaveAnalyticsSpy,
                instance;

            beforeEach(function () {
                instance = new viewModels.ExportInstance(basicFormExport);
                recordSaveAnalyticsSpy = sinon.spy();
                server = sinon.fakeServer.create();

                sinon.stub(instance, 'recordSaveAnalytics', recordSaveAnalyticsSpy);
            });

            afterEach(function () {
                server.restore();
                instance.recordSaveAnalytics.restore();
            });

            it('Should save a model', function () {
                server.respondWith(
                    "POST",
                    instance.saveUrl,
                    [
                        200,
                        { "Content-Type": "application/json" },
                        '{ "redirect": "http://dummy/"}',
                    ]
                );

                assert.equal(instance.saveState(), constants.SAVE_STATES.READY);
                instance.save();

                assert.equal(instance.saveState(), constants.SAVE_STATES.SAVING);
                server.respond();

                assert.isTrue(recordSaveAnalyticsSpy.called);
            });

            it('Should crash on saving export', function () {
                server.respondWith(
                    "POST",
                    instance.saveUrl,
                    [
                        500,
                        { "Content-Type": "application/json" },
                        '{ "status": "fail" }',
                    ]
                );
                instance.save();

                assert.equal(instance.saveState(), constants.SAVE_STATES.SAVING);
                server.respond();

                assert.equal(instance.saveState(), constants.SAVE_STATES.ERROR);
                assert.isFalse(recordSaveAnalyticsSpy.called);
            });

        });
    });
});
