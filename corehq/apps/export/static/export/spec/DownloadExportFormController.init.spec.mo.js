describe('DownloadExportFormController - Initialization', function() {
    DnldExpData.prepareTests();
    DnldExpData.prepareDownloadController();

    beforeEach(function () {
        DnldExpData.$httpBackend
            .when('POST', DnldExpData.mockBackendUrls.HAS_MULTIMEDIA)
            .respond({
                success: true,
                hasMultimedia: true
            });
    });

    afterEach(function () {
        DnldExpData.$httpBackend.verifyNoOutstandingExpectation();
        DnldExpData.$httpBackend.verifyNoOutstandingRequest();
    });

    it('checks for multimedia', function () {
        DnldExpData.$httpBackend
            .when('POST', DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS)
            .respond({
                success: true,
                groups: DnldExpData.groupList
            });
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.HAS_MULTIMEDIA);
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS);
        DnldExpData.createController([
            DnldExpData.simpleFormExport
        ], true);
        DnldExpData.$httpBackend.flush();
        assert.isTrue(DnldExpData.currentScope.hasMultimedia);
    });

    it('fetches group options', function () {
        DnldExpData.$httpBackend
            .when('POST', DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS)
            .respond({
                success: true,
                groups: DnldExpData.groupList
            });
        DnldExpData.createController([
            DnldExpData.simpleFormExport
        ], true);
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.HAS_MULTIMEDIA);
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS);
        assert.isTrue(DnldExpData.currentScope.groupsLoading);
        DnldExpData.$httpBackend.flush();
        assert.isFalse(DnldExpData.currentScope.groupsLoading);
        assert.isTrue(DnldExpData.currentScope.hasGroups);
    });

    it('registers group options error', function () {
        DnldExpData.$httpBackend
            .when('POST', DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS)
            .respond({
                error: 'error fetching groups in test'
            });
        DnldExpData.createController([
            DnldExpData.simpleFormExport
        ], true);
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.HAS_MULTIMEDIA);
        DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS);
        assert.isTrue(DnldExpData.currentScope.groupsLoading);
        DnldExpData.$httpBackend.flush();
        assert.isFalse(DnldExpData.currentScope.groupsLoading);
        assert.isFalse(DnldExpData.currentScope.hasGroups);
        assert.isTrue(DnldExpData.currentScope.groupsError);
    });

});
