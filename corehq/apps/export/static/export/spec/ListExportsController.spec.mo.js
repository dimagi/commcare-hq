describe('ListExportsController Unit Tests', function () {
    var $httpBackend, createController, $rootScope, currentScope;

    var mockBackendUrls = {
        UPDATE_EMAILED_EXPORT_DATA: '/fake/exports/update/data',
        TOGGLE_SAVED_EXPORT_ENABLED_STATE: '/fake/exports/toggle_enabled',
        GET_SAVED_EXPORT_PROGRESS: '/fake/exports/get_progress',
    };

    hqImport("hqwebapp/js/initial_page_data").register("exports", [
        ListExportsTestData.exportWithFileData,
        ListExportsTestData.exportDeId,
        ListExportsTestData.exportSimple,
    ]);

    beforeEach(function () {
        var listExportsTestApp = angular.module('ngtest.ListExportsApp', ['hq.list_exports']);
        listExportsTestApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
            djangoRMIProvider.configure({
                update_emailed_export_data: {
                    url: mockBackendUrls.UPDATE_EMAILED_EXPORT_DATA,
                    headers: {
                        'DjNg-Remote-Method': 'update_emailed_export_data',
                    },
                    method: 'auto',
                },
                toggle_saved_export_enabled_state: {
                    url: mockBackendUrls.TOGGLE_SAVED_EXPORT_ENABLED_STATE,
                    headers: {
                        'DjNg-Remote-Method': 'toggle_saved_export_enabled_state',
                    },
                    method: 'auto',
                },
                get_saved_export_progress: {
                    url: mockBackendUrls.GET_SAVED_EXPORT_PROGRESS,
                    headers: {
                        'DjNg-Remote-Method': 'get_saved_export_progress',
                    },
                    method: 'auto',
                },
            });
        }]);
        listExportsTestApp.constant('bulk_download_url', "/fake/bulk/download/url");
        listExportsTestApp.constant('legacy_bulk_download_url', "/fake/legacy/bulk/download/url");
        listExportsTestApp.constant('modelType', null);
        module('ngtest.ListExportsApp');
        // Kickstart the injectors previously registered with calls to angular.mock.module
        inject(function () {});
    });

    beforeEach(inject(function ($injector) {
        $rootScope = $injector.get('$rootScope');
        $httpBackend = $injector.get('$httpBackend');
        var $controller = $injector.get('$controller');
        createController = function () {
            currentScope = $rootScope.$new();
            return $controller('ListExportsController', {'$scope': currentScope});
        };
    }));

    describe("Actions", function () {

        beforeEach(function () {
            $httpBackend
                .when('POST', mockBackendUrls.GET_SAVED_EXPORT_PROGRESS)
                .respond({
                    success: true,
                    taskStatus: {
                        percentComplete: 20,
                        inProgress: true,
                        success: false,
                    },
                });
        });

        afterEach(function () {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('selectAll()', function () {
            createController();

            assert.equal(currentScope.bulkExportList.length, 2);
            assert.isFalse(currentScope.showBulkExportDownload);
            currentScope.selectAll();
            assert.isAbove(currentScope.bulkExportList.length, 2);
            assert.isTrue(currentScope.showBulkExportDownload);
        });

        it('selectNone()', function () {
            createController();

            assert.equal(currentScope.bulkExportList.length, 2);
            assert.isFalse(currentScope.showBulkExportDownload);
            currentScope.selectAll();
            assert.isAbove(currentScope.bulkExportList.length, 2);
            assert.isTrue(currentScope.showBulkExportDownload);
            currentScope.selectNone();
            assert.equal(currentScope.bulkExportList.length, 2);
            assert.isFalse(currentScope.showBulkExportDownload);
        });
        describe('updateEmailedExportData()', function () {
            var exportToUpdate, component;

            beforeEach(function () {
                $httpBackend
                    .when('POST', mockBackendUrls.UPDATE_EMAILED_EXPORT_DATA)
                    .respond({
                        success: true,
                    });
                createController();
                $httpBackend.expectPOST(mockBackendUrls.UPDATE_EMAILED_EXPORT_DATA);
                exportToUpdate = currentScope.exports[0];
                component = exportToUpdate.emailedExport;
                currentScope.updateEmailedExportData(component, exportToUpdate);
            });

            it('success ok', function () {
                assert.isTrue(component.updatingData);
                $httpBackend.flush();
                assert.isFalse(component.updatingData);
                assert.isTrue(component.taskStatus.inProgress);
            });

            it('analytics ok', function () {
                assert.isTrue(hqImport('analytix/js/google').track.event.calledWith("Form Exports", "Update Saved Export", "Saved"));
                $httpBackend.flush();
            });
        });
        describe('updateDisabledState()', function () {
            var exportToUpdate, component;

            beforeEach(function () {
                $httpBackend
                    .when('POST', mockBackendUrls.TOGGLE_SAVED_EXPORT_ENABLED_STATE)
                    .respond({
                        success: true,
                        isAutoRebuildEnabled: false,
                    });
                createController();
                $httpBackend.expectPOST(mockBackendUrls.TOGGLE_SAVED_EXPORT_ENABLED_STATE);
                exportToUpdate = currentScope.exports[0];
                component = exportToUpdate.emailedExport;
                currentScope.updateDisabledState(component, exportToUpdate);
            });

            it('success ok', function () {
                assert.isTrue(component.savingAutoRebuildChange);
                $httpBackend.flush();
                assert.isFalse(component.savingAutoRebuildChange);
                assert.isFalse(exportToUpdate.isAutoRebuildEnabled);
            });

            it('analytics ok', function () {
                assert.isTrue(hqImport('analytix/js/google').track.event.calledWith("Form Exports", "Disable Saved Export", "Saved"));
                $httpBackend.flush();
            });
        });
    });

});
