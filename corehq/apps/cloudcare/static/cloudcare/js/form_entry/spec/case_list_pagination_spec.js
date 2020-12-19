describe('#paginateOptions', function () {
    var paginateItems = hqImport("cloudcare/js/formplayer/menus/views");
    it('Should return paginateOptions', function () {
        var result = paginateItems.paginateOptions(0, 15);
        /**
         *   result: {stratPage:'', endPage:'', pageCount:''}
         *   endPage: max number of pages to display at a time
         *   pageCount: total number of pages
         */

        //Asserting equal
        assert.equal(result.startPage, 1);
        assert.equal(result.endPage, 5);
        assert.equal(result.pageCount, 15);

        //Asserting not equal
        assert.notEqual(result.startPage, 5);
        assert.notEqual(result.endPage, 10);
        assert.notEqual(result.pageCount, 20);


    });
});
