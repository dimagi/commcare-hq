describe('Reach Utils', function () {
    var reachUtils;

    beforeEach(function () {
        reachUtils = hqImport('aaa/js/utils/reach_utils').reachUtils();
    });

    it('test india format', function () {
        var number = reachUtils.toIndiaFormat('123456789');
        assert.equal(number, '12,34,56,789');
    });
});
