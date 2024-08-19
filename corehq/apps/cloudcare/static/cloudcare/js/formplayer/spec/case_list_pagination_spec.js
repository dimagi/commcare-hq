'use strict';
hqDefine("cloudcare/js/formplayer/spec/case_list_pagination_spec", [
    "cloudcare/js/formplayer/utils/utils",
], function (
    paginateItems
) {
    describe('#paginateOptions', function () {
        it('Should return paginateOptions', function () {
            var case1 = paginateItems.paginateOptions(0, 15, 3);
            /**
             *   result: {startPage:'', endPage:'', pageCount:''}
             *   endPage: max number of pages to display at a time
             *   pageCount: total number of pages
             */

            //Asserting equal
            assert.equal(case1.startPage, 1);
            assert.equal(case1.endPage, 5);
            assert.equal(case1.pageCount, 15);

            var case2 = paginateItems.paginateOptions(4, 10, 7);

            //Asserting equal
            assert.equal(case2.startPage, 2);
            assert.equal(case2.endPage, 6);
            assert.equal(case2.pageCount, 10);
            assert.equal(case2.showPagination, true);

            var case3 = paginateItems.paginateOptions(-1, 10, 5);

            //Asserting equal
            assert.equal(case3.startPage, 1);
            assert.equal(case3.endPage, 5);
            assert.equal(case3.pageCount, 10);
            assert.equal(case3.showPagination, true);

            var case4 = paginateItems.paginateOptions(10, 10);

            //Asserting equal
            assert.equal(case4.startPage, 6);
            assert.equal(case4.endPage, 10);
            assert.equal(case4.pageCount, 10);

            var case5 = paginateItems.paginateOptions(1, 1, 5);
            assert.equal(case5.showPagination, false);
        });
    });
});
