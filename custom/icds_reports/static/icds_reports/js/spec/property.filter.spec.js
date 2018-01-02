/* global module, inject, chai */
"use strict";

describe('Property Filter', function () {

    var $filter;

    beforeEach(function () {
        module('icdsApp');

        inject(function (_$filter_) {
            $filter = _$filter_;
        });
    });

    it('tests instantiate the filter properly', function () {
        chai.expect($filter).not.to.be.a('undefined');
    });

    it('tests filter when not array', function () {
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
