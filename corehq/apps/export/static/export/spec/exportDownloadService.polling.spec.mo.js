describe('DownloadExportFormController -> exportDownloadService - Polling', function() {
    DnldExpData.prepareTests();
    DnldExpData.prepareDownloadController();
    DnldExpData.prepareBackends();
    var downloadId = 'uuid-errorsTest';

    beforeEach(function () {
        DnldExpData.$httpBackend
            .when('POST', DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT)
            .respond({
                success: true,
                download_id: downloadId
            });
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT);
    });

    describe('Progress Error', function () {
        var progressErrorResponse = DnldExpData.getPollResponseProgressError(downloadId);

        beforeEach(function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD)
                .respond(progressErrorResponse);
            DnldExpData.$interval.flush(2000);  // start polling
            DnldExpData.$httpBackend.flush();   // get polling response
        });

        it('poll stops on progress error, registers error', function () {
            DnldExpData.$interval.flush(2000);  // poll again
            assert.throw(DnldExpData.$httpBackend.flush); // response should error
            assert.equal(DnldExpData.exportDownloadService.downloadError, progressErrorResponse.progress.error);
        });

        it('registers a reset', function () {
            assert.equal(DnldExpData.exportDownloadService.downloadError, progressErrorResponse.progress.error);
            DnldExpData.exportDownloadService.resetDownload();
            DnldExpData.currentScope.$apply();
            assert.isNull(DnldExpData.exportDownloadService.downloadError);
        });
    });

    describe('General Error', function () {
        var errorResponse = DnldExpData.getPollResponseError(downloadId);

        beforeEach(function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD)
                .respond(errorResponse);
            DnldExpData.$interval.flush(2000);  // start polling
            DnldExpData.$httpBackend.flush();   // first response, throws error attempts retries
            // retry 3 times
            for (var r=0; r < 3; r++) {
                DnldExpData.$interval.flush(2000);
                DnldExpData.$httpBackend.flush();
                assert.isNull(DnldExpData.exportDownloadService.downloadError);
            }
            // on 4th retry, show download error
            DnldExpData.$interval.flush(2000);
            DnldExpData.$httpBackend.flush();
        });

        it('poll stops on general download error after 4th retry, registers error', function () {
            assert.equal(DnldExpData.exportDownloadService.downloadError, errorResponse.error);
            // make sure polling stops
            DnldExpData.$interval.flush(2000);
            assert.throw(DnldExpData.$httpBackend.flush);
        });

        it('registers a reset', function () {
            assert.equal(DnldExpData.exportDownloadService.downloadError, errorResponse.error);
            assert.equal(DnldExpData.exportDownloadService._numErrors, 5);
            DnldExpData.exportDownloadService.resetDownload();
            DnldExpData.currentScope.$apply();
            assert.isNull(DnldExpData.exportDownloadService.downloadError);
            assert.equal(DnldExpData.exportDownloadService._numErrors, 0);
        });
    });

    describe('Celery Error', function () {

        beforeEach(function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD)
                .respond(DnldExpData.getPollResponseCeleryError(downloadId));
            DnldExpData.$interval.flush(2000);  // start polling
            DnldExpData.$httpBackend.flush();   // first response, throws error attempts retries
            // retry 10 times
            for (var r=0; r < 10; r++) {
                DnldExpData.$interval.flush(2000);
                DnldExpData.$httpBackend.flush();
                assert.isFalse(DnldExpData.exportDownloadService.showCeleryError);
            }
            // on 11th retry, throw celery error
            DnldExpData.$interval.flush(2000);
            DnldExpData.$httpBackend.flush();
        });

        it('poll stops on celery error after 11th retry, registers celery error', function () {
            assert.isTrue(DnldExpData.exportDownloadService.showCeleryError);
            // make sure polling stops
            DnldExpData.$interval.flush(2000);
            assert.throw(DnldExpData.$httpBackend.flush);
        });

        it('registers a reset', function () {
            assert.isTrue(DnldExpData.exportDownloadService.showCeleryError);
            assert.equal(DnldExpData.exportDownloadService._numCeleryRetries, 12);
            DnldExpData.exportDownloadService.resetDownload();
            DnldExpData.currentScope.$apply();
            assert.isFalse(DnldExpData.exportDownloadService.showCeleryError);
            assert.equal(DnldExpData.exportDownloadService._numCeleryRetries, 0);
        });
    });

    describe('HTTP Error', function () {
        beforeEach(function () {
            DnldExpData.createController([
                DnldExpData.simpleFormExport
            ], true);
            DnldExpData.currentScope.prepareExport();
            DnldExpData.$httpBackend.flush();
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD)
                .respond(503);
            DnldExpData.$interval.flush(2000);  // start polling
            DnldExpData.$httpBackend.flush();   // first response, throws error attempts retries
            // retry 3 times
            for (var r=0; r < 3; r++) {
                DnldExpData.$interval.flush(2000);
                DnldExpData.$httpBackend.flush();
                assert.isNull(DnldExpData.exportDownloadService.downloadError);
            }
            // on 4th retry, show 'default' download error
            DnldExpData.$interval.flush(2000);
            DnldExpData.$httpBackend.flush();
        });

        it('poll stops on errored HTTP response on 4th retry, registers error', function () {
            assert.equal(DnldExpData.exportDownloadService.downloadError, 'default');
            // make sure polling stops
            DnldExpData.$interval.flush(2000);
            assert.throw(DnldExpData.$httpBackend.flush);
        });

        it('registers a reset', function () {
            assert.equal(DnldExpData.exportDownloadService.downloadError, 'default');
            assert.equal(DnldExpData.exportDownloadService._numErrors, 5);
            DnldExpData.exportDownloadService.resetDownload();
            DnldExpData.currentScope.$apply();
            assert.isNull(DnldExpData.exportDownloadService.downloadError);
            assert.equal(DnldExpData.exportDownloadService._numErrors, 0);
        });
    });
});
