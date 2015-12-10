describe('DownloadProgressController', function() {
    DnldExpData.prepareTests();
    DnldExpData.prepareDownloadProgressController();
    describe('$watch on exportDownloadService', function () {
        beforeEach(function () {
            DnldExpData.createProgressController();
            assert.isFalse(DnldExpData.currentScope.showProgress);
            assert.isFalse(DnldExpData.currentScope.showDownloadStatus);
            assert.isFalse(DnldExpData.currentScope.isDownloadReady);
            assert.isFalse(DnldExpData.currentScope.isDownloaded);
            assert.isNull(DnldExpData.currentScope.dropboxUrl);
            assert.isNull(DnldExpData.currentScope.downloadUrl);
            assert.deepEqual(DnldExpData.currentScope.progress, {});
        });

        describe('showDownloadStatus', function () {
            beforeEach(function () {
                assert.isFalse(DnldExpData.exportDownloadService.showDownloadStatus);
                DnldExpData.exportDownloadService.showDownloadStatus = true;
                DnldExpData.currentScope.$apply();
            });

            it('update ok', function () {
                assert.isTrue(DnldExpData.exportDownloadService.showDownloadStatus);
                assert.isTrue(DnldExpData.currentScope.showDownloadStatus);
            });

            it('reset ok', function () {
                DnldExpData.currentScope.resetDownload();
                DnldExpData.currentScope.$apply();
                assert.isFalse(DnldExpData.exportDownloadService.showDownloadStatus);
                assert.isFalse(DnldExpData.currentScope.showDownloadStatus);
            });
        });

        describe('showCeleryError', function () {
            beforeEach(function () {
                assert.isFalse(DnldExpData.exportDownloadService.showCeleryError);
                DnldExpData.exportDownloadService.showCeleryError = true;
                DnldExpData.currentScope.$apply();
            });

            it('update ok', function () {
                assert.isTrue(DnldExpData.exportDownloadService.showCeleryError);
                assert.isTrue(DnldExpData.currentScope.showCeleryError);
            });

            it('reset ok', function () {
                DnldExpData.currentScope.resetDownload();
                DnldExpData.currentScope.$apply();
                assert.isFalse(DnldExpData.exportDownloadService.showCeleryError);
                assert.isFalse(DnldExpData.currentScope.showCeleryError);
            });
        });

        describe('isMultimediaDownload', function () {
            beforeEach(function () {
                assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);
                DnldExpData.exportDownloadService.isMultimediaDownload = true;
                DnldExpData.currentScope.$apply();
            });

            it('update ok', function () {
                assert.isTrue(DnldExpData.exportDownloadService.isMultimediaDownload);
                assert.isTrue(DnldExpData.currentScope.isMultimediaDownload);
            });

            it('reset ok', function () {
                DnldExpData.currentScope.resetDownload();
                DnldExpData.currentScope.$apply();
                assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);
                assert.isFalse(DnldExpData.currentScope.isMultimediaDownload);
            });
        });

        describe('downloadStatusData', function () {
            beforeEach(function () {
                assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);
                DnldExpData.exportDownloadService.isMultimediaDownload = true;
                DnldExpData.currentScope.$apply();
            });

            it('update ok', function () {
                assert.isTrue(DnldExpData.exportDownloadService.isMultimediaDownload);
                assert.isTrue(DnldExpData.currentScope.isMultimediaDownload);
            });

            it('reset ok', function () {
                DnldExpData.currentScope.resetDownload();
                DnldExpData.currentScope.$apply();
                assert.isFalse(DnldExpData.exportDownloadService.isMultimediaDownload);
                assert.isFalse(DnldExpData.currentScope.isMultimediaDownload);
            });
        });

        describe('downloadStatusData', function () {
            var downloadId = 'uuid-downloadStatusCheck';
            beforeEach(function () {
                assert.deepEqual(DnldExpData.currentScope.progress, {});
            });
            it('registers progress', function () {
                DnldExpData.exportDownloadService.downloadStatusData = DnldExpData.getPollResponseProgress(downloadId);
                DnldExpData.currentScope.$apply();
                assert.isTrue(DnldExpData.currentScope.showProgress);
                assert.deepEqual(DnldExpData.currentScope.progress, DnldExpData.exportDownloadService.downloadStatusData.progress);
                assert.equal(DnldExpData.currentScope.progress.percent, 10);
                assert.isFalse(DnldExpData.currentScope.isDownloadReady);
                assert.isNull(DnldExpData.currentScope.dropboxUrl);
                assert.isNull(DnldExpData.currentScope.downloadUrl);
            });
            describe('on success', function () {
                beforeEach(function () {
                    DnldExpData.exportDownloadService.downloadStatusData = DnldExpData.getPollResponseSuccess(downloadId);
                    DnldExpData.currentScope.$apply();
                });
                it('update ok', function () {
                    assert.isTrue(DnldExpData.currentScope.showProgress);
                    assert.deepEqual(DnldExpData.currentScope.progress, DnldExpData.exportDownloadService.downloadStatusData.progress);
                    assert.equal(DnldExpData.currentScope.progress.percent, 100);
                    assert.isTrue(DnldExpData.currentScope.isDownloadReady);
                    assert.isNotNull(DnldExpData.currentScope.dropboxUrl);
                    assert.isNotNull(DnldExpData.currentScope.downloadUrl);
                });
                it('reset ok', function () {
                    DnldExpData.currentScope.resetDownload();
                    DnldExpData.currentScope.$apply();
                    assert.isFalse(DnldExpData.currentScope.showProgress);
                    assert.deepEqual(DnldExpData.currentScope.progress, {});
                    assert.isFalse(DnldExpData.currentScope.isDownloadReady);
                    assert.isNull(DnldExpData.currentScope.dropboxUrl);
                    assert.isNull(DnldExpData.currentScope.downloadUrl);
                });

                it('test analytics', function () {
                    DnldExpData.exportDownloadService.exportType = 'form';
                    DnldExpData.currentScope.sendAnalytics();
                    assert.isTrue(analytics.usage.lastCall.calledWith("Download Export", "Form", "Saved"));
                    assert.isTrue(analytics.workflow.lastCall.calledWith("Clicked Download button"));
                });
            });
        });
    });
});
