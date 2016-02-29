describe('ListExportsController Unit Tests', function() {
    var $httpBackend, createController, $rootScope, currentScope;

    var mockBackendUrls = {
        GET_EXPORTS_LIST: '/fake/exports/list',
        UPDATE_EMAILED_EXPORT_DATA: '/fake/exports/update/data'
    };

    beforeEach(function () {
        var listExportsTestApp = angular.module('ngtest.ListExportsApp', ['hq.list_exports']);
        listExportsTestApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
            djangoRMIProvider.configure({
                get_exports_list: {
                    url: mockBackendUrls.GET_EXPORTS_LIST,
                    headers: {
                        'DjNg-Remote-Method': 'get_exports_list'
                    },
                    method: 'auto'
                },
                update_emailed_export_data: {
                    url: mockBackendUrls.UPDATE_EMAILED_EXPORT_DATA,
                    headers: {
                        'DjNg-Remote-Method': 'update_emailed_export_data'
                    },
                    method: 'auto'
                }
            });
        }]);
        module('ngtest.ListExportsApp');
        // Kickstart the injectors previously registered with calls to angular.mock.module
        inject(function () {});
    });

    beforeEach(inject(function($injector) {
        $rootScope = $injector.get('$rootScope');
        $httpBackend = $injector.get('$httpBackend');
        var $controller = $injector.get('$controller');
        createController = function () {
            currentScope = $rootScope.$new();
            return $controller('ListExportsController', {'$scope': currentScope});
        };

    }));

    describe('Initialization', function() {

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('registers a non-blank list of exports', function() {
            $httpBackend
                .when('POST', mockBackendUrls.GET_EXPORTS_LIST)
                .respond({
                    success: true,
                    exports: [ListExportsTestData.exportSimple]
                });
            createController();
            assert.equal(currentScope.exports.length, 0);
            assert.isFalse(currentScope.hasLoaded);
            $httpBackend.expectPOST(mockBackendUrls.GET_EXPORTS_LIST);
            $httpBackend.flush();
            assert.equal(currentScope.exports.length, 1);
            assert.isTrue(currentScope.hasLoaded);
        });

        it('registers a server-side error', function() {
            var serverErrorMsg = 'error initializing exports for test';
            $httpBackend
                .when('POST', mockBackendUrls.GET_EXPORTS_LIST)
                .respond({
                    error: serverErrorMsg
                });
            createController();
            assert.equal(currentScope.exports.length, 0);
            assert.isFalse(currentScope.hasLoaded);
            $httpBackend.expectPOST(mockBackendUrls.GET_EXPORTS_LIST);
            $httpBackend.flush();
            assert.equal(currentScope.exports.length, 0);
            assert.isTrue(currentScope.hasLoaded);
            assert.equal(serverErrorMsg, currentScope.exportsListError);
        });

        it('registers a connection error', function() {
            $httpBackend
                .when('POST', mockBackendUrls.GET_EXPORTS_LIST)
                .respond(522, '');
            createController();
            $httpBackend.expectPOST(mockBackendUrls.GET_EXPORTS_LIST);
            $httpBackend.flush();
            assert.equal(currentScope.exports.length, 0);
            assert.isTrue(currentScope.hasLoaded);
            assert.equal('default', currentScope.exportsListError);
        });

    });

    describe("Actions", function () {

        beforeEach(function () {
            $httpBackend
                .when('POST', mockBackendUrls.GET_EXPORTS_LIST)
                .respond({
                    success: true,
                    exports: [
                        ListExportsTestData.exportWithFileData,
                        ListExportsTestData.exportDeId,
                        ListExportsTestData.exportSimple
                    ]
                });
        });

        afterEach(function() {
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        it('selectAll()', function() {
            createController();
            $httpBackend.expectPOST(mockBackendUrls.GET_EXPORTS_LIST);
            $httpBackend.flush();

            assert.equal(currentScope.bulkExportList.length, 2);
            assert.isFalse(currentScope.showBulkExportDownload);
            currentScope.selectAll();
            assert.isAbove(currentScope.bulkExportList.length, 2);
            assert.isTrue(currentScope.showBulkExportDownload);
        });

        it('selectNone()', function() {
            createController();
            $httpBackend.expectPOST(mockBackendUrls.GET_EXPORTS_LIST);
            $httpBackend.flush();

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
                    success: true
                });
                createController();
                $httpBackend.expectPOST(mockBackendUrls.GET_EXPORTS_LIST);
                $httpBackend.flush();
                $httpBackend.expectPOST(mockBackendUrls.UPDATE_EMAILED_EXPORT_DATA);
                exportToUpdate = currentScope.exports[0];
                component = exportToUpdate.emailedExports[0];
                currentScope.updateEmailedExportData(component, exportToUpdate);
            });

            it('success ok', function() {
                assert.isTrue(component.updatingData);
                $httpBackend.flush();
                assert.isFalse(component.updatingData);
                assert.isTrue(component.updatedDataTriggered);
            });

            it('analytics ok', function() {
                assert.isTrue(analytics.usage.calledWith("Update Saved Export", "Form", "Saved"));
                $httpBackend.flush();
            });
        });
    });

});
