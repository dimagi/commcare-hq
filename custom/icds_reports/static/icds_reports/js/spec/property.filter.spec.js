/* global module, inject */
"use strict";

describe('PropertyFilter', function () {

    var $filter;

    beforeEach(function () {
        module('icdsApp');

        inject(function (_$filter_) {
            $filter = _$filter_;
        });
    });

    it('should filter when not array', function () {
        // Arrange.
        var testValue = { id: '1'};

        // Act.
        var result = $filter('propsFilter')(testValue, null);

        //Expected
        var expected = { id: '1'};

        // Assert.
        assert.deepEqual(expected, result);
    });
});
