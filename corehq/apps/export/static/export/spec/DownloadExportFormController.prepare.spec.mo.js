describe('DownloadExportFormController - Prepare Download', function() {
    DnldExpData.prepareTests();
    DnldExpData.prepareDownloadController();
    DnldExpData.prepareBackends();
    var downloadId = 'uuid-downloadTest';

    describe('Standard Operation', function () {
        beforeEach(function () {
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT)
                .respond({
                    success: true,
                    download_id: downloadId
                });
            DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT);
        });

        it('trigger downloadInProgress', function() {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            assert.equal(DnldExpData.currentScope.prepareExportError, null);
            assert.isTrue(DnldExpData.currentScope.preparingExport);
            DnldExpData.$httpBackend.flush();
            assert.isFalse(DnldExpData.currentScope.preparingExport);
            assert.isTrue(DnldExpData.currentScope.downloadInProgress);
            var lastCallNum = analytics.usage.callCount - 1;
            var userTypeCall = analytics.usage.getCall(lastCallNum - 1);
            assert.isTrue(userTypeCall.calledWith("Download Export", 'Select "user type"', "mobile"));
            assert.isTrue(analytics.usage.lastCall.calledWith("Download Export", "Form", "Regular"));
            assert.isTrue(analytics.workflow.lastCall.calledWith("Clicked Prepare Export"));
        });

        it('user type analytics', function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            var testUserTypes = ['mobile', 'demo', 'admin'];
            DnldExpData.currentScope.formData.user_types = testUserTypes;
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            assert.isTrue(analytics.usage.lastCall.calledWith("Download Export", "Form", "Regular"));
            var lastCallNum = analytics.usage.callCount - 1;
            for (var i = 1; i < 4; i++) {
                var userTypeCall = analytics.usage.getCall(lastCallNum - i);
                assert.isTrue(userTypeCall.calledWith("Download Export", 'Select "user type"', testUserTypes[testUserTypes.length - i]));
            }
            assert.isTrue(analytics.workflow.lastCall.calledWith("Clicked Prepare Export"));
        });

        it('bulk form analytics', function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport,
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            assert.isTrue(analytics.usage.lastCall.calledWith("Download Export", "Form", "Bulk"));
            assert.isTrue(analytics.workflow.lastCall.calledWith("Clicked Prepare Export"));
        });

        it('start exportDownloadService', function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            assert.isFalse(DnldExpData.exportDownloadService.showDownloadStatus);
            assert.isFalse(DnldExpData.currentScope.downloadInProgress);
            DnldExpData.$httpBackend.flush();
            assert.isTrue(DnldExpData.exportDownloadService.showDownloadStatus);
            assert.isTrue(DnldExpData.currentScope.downloadInProgress);
            assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);
            assert.equal(DnldExpData.exportDownloadService.downloadId, downloadId);
            assert.isTrue(analytics.workflow.lastCall.calledWith("Clicked Prepare Export"));
        });

        it('poll download progress', function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD)
                .respond(DnldExpData.getPollResponseProgress(downloadId));
            DnldExpData.$interval.flush(2000);  // start polling
            DnldExpData.$httpBackend.flush();   // get polling response
            DnldExpData.$interval.flush(2000);  // poll again
            DnldExpData.$httpBackend.flush();   // poll should continue
        });

        describe('On Success', function () {
            var successfulResponse = DnldExpData.getPollResponseSuccess(downloadId);
            beforeEach(function () {
                DnldExpData.createController([
                    DnldExpData.simpleFormExport
                ], true);
                DnldExpData.currentScope.prepareExport();
                DnldExpData.$httpBackend.flush();
                DnldExpData.$httpBackend
                    .when('POST', DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD)
                    .respond(successfulResponse);
                DnldExpData.$interval.flush(2000);  // start polling
                DnldExpData.$httpBackend.flush();   // get polling response
            });

            it('polling stops', function () {
                DnldExpData.$interval.flush(2000);  // poll again
                assert.throw(DnldExpData.$httpBackend.flush); // response should error
                assert.deepEqual(DnldExpData.exportDownloadService.downloadStatusData, successfulResponse);
            });

            it('exportDownloadService.resetDownload() is registered by controller', function () {
                assert.isNotNull(DnldExpData.exportDownloadService.downloadId);
                assert.isTrue(DnldExpData.exportDownloadService.showDownloadStatus);
                assert.isTrue(DnldExpData.currentScope.downloadInProgress);
                assert.isNotNull(DnldExpData.exportDownloadService.downloadStatusData);
                assert.isNotNull(DnldExpData.exportDownloadService.exportType);

                // no error functions happened
                assert.equal(DnldExpData.exportDownloadService._numErrors, 0);
                assert.equal(DnldExpData.exportDownloadService._numCeleryRetries, 0);
                assert.isNull(DnldExpData.exportDownloadService.downloadError);
                assert.isFalse(DnldExpData.exportDownloadService.showCeleryError);
                assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);

                DnldExpData.exportDownloadService.resetDownload();
                DnldExpData.currentScope.$apply();  // triggers $watch
                assert.isNull(DnldExpData.exportDownloadService.downloadId);
                assert.isFalse(DnldExpData.exportDownloadService.showDownloadStatus);
                assert.isFalse(DnldExpData.currentScope.downloadInProgress);
                assert.isNull(DnldExpData.exportDownloadService.downloadStatusData);
                assert.isNull(DnldExpData.exportDownloadService.exportType);

                // this remains the same
                assert.equal(DnldExpData.exportDownloadService._numErrors, 0);
                assert.equal(DnldExpData.exportDownloadService._numCeleryRetries, 0);
                assert.isNull(DnldExpData.exportDownloadService.downloadError);
                assert.isFalse(DnldExpData.exportDownloadService.showCeleryError);
                assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);
            });
        });
    });

    describe('Error Handling', function () {
        it('registers server error', function () {
            var errorMsg = 'server error test';
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT)
                .respond({
                    error: errorMsg
                });
            DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT);
            DnldExpData.currentScope.prepareExport();
            assert.isTrue(DnldExpData.currentScope.preparingExport);
            assert.isNull(DnldExpData.currentScope.prepareExportError);
            DnldExpData.$httpBackend.flush();
            assert.throw(DnldExpData.$httpBackend.flush); // no polling happens
            assert.isFalse(DnldExpData.currentScope.preparingExport);
            assert.equal(DnldExpData.currentScope.prepareExportError, errorMsg);
        });

        it('registers HTTP error', function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT)
                .respond(503);
            DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT);
            DnldExpData.currentScope.prepareExport();
            assert.isTrue(DnldExpData.currentScope.preparingExport);
            assert.isNull(DnldExpData.currentScope.prepareExportError);
            DnldExpData.$httpBackend.flush();
            assert.throw(DnldExpData.$httpBackend.flush); // no polling happens
            assert.isFalse(DnldExpData.currentScope.preparingExport);
            assert.equal(DnldExpData.currentScope.prepareExportError, 'default');
        });
    });
});
