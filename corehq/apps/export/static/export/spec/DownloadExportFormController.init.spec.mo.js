/* globals DnldExpData */
describe('DownloadExportFormController - Initialization', function () {
    DnldExpData.prepareTests();
    DnldExpData.prepareDownloadController();

    beforeEach(function () {
        DnldExpData.$httpBackend
            .when('POST', DnldExpData.mockBackendUrls.HAS_MULTIMEDIA)
            .respond({
                success: true,
                hasMultimedia: true,
            });
    });

    afterEach(function () {
        DnldExpData.$httpBackend.verifyNoOutstandingExpectation();
        DnldExpData.$httpBackend.verifyNoOutstandingRequest();
    });

    it('checks for multimedia', function () {
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.HAS_MULTIMEDIA);
        DnldExpData.createController([
            DnldExpData.simpleFormExport,
        ], true);
        DnldExpData.$httpBackend.flush();
        assert.isTrue(DnldExpData.currentScope.hasMultimedia);
    });

});
