hqDefine("cloudcare/js/form_entry/spec/case_list_pagination_spec", function () {
    describe('#paginateOptions', function () {
        var paginateItems = hqImport("cloudcare/js/formplayer/utils/utils");
        it('Should return paginateOptions', function () {
            var case1 = paginateItems.paginateOptions(0, 15);
            /**
             *   result: {startPage:'', endPage:'', pageCount:''}
             *   endPage: max number of pages to display at a time
             *   pageCount: total number of pages
             */

            //Asserting equal
            assert.equal(case1.startPage, 1);
            assert.equal(case1.endPage, 5);
            assert.equal(case1.pageCount, 15);

            //Asserting not equal
            assert.notEqual(case1.startPage, 5);
            assert.notEqual(case1.endPage, 10);
            assert.notEqual(case1.pageCount, 20);

            var case2 = paginateItems.paginateOptions(4, 10);

            //Asserting equal
            assert.equal(case2.startPage, 2);
            assert.equal(case2.endPage, 6);
            assert.equal(case2.pageCount, 10);

            //Asserting not equal
            assert.notEqual(case2.startPage, 7);
            assert.notEqual(case2.endPage, 9);
            assert.notEqual(case2.pageCount, 3);

            var case3 = paginateItems.paginateOptions(-1, 10);

            //Asserting equal
            assert.equal(case3.startPage, 1);
            assert.equal(case3.endPage, 5);
            assert.equal(case3.pageCount, 10);

            var case4 = paginateItems.paginateOptions(10, 10);

            //Asserting equal
            assert.equal(case4.startPage, 6);
            assert.equal(case4.endPage, 10);
            assert.equal(case4.pageCount, 10);
        });
    });
});
