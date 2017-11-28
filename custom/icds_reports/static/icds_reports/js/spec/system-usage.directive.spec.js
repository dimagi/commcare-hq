/* global d3, module, inject */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('SystemUsageDirective', function () {

    var $scope, $httpBackend, $location, controller;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('program_summary', 'program_summary');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
    }));

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('program_summary').respond(200, {
            report_data: ['report_test_data'],
        });
        var element = window.angular.element("<system-usage data='test'></system-usage>");
        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('systemUsage');
        controller.step = 'maternal_child';
    }));


    it('tests initial state', function () {
        assert.equal(controller.step, 'maternal_child');
        assert.equal(controller.steps['maternal_child'].label, 'Maternal and Child Nutrition');
        assert.deepEqual(controller.filtersData, {});
    });

    it('tests moveToLocation national', function () {
        controller.moveToLocation('national', -1);

        var searchData = $location.search();

        assert.equal(searchData.location_id, '');
        assert.equal(searchData.selectedLocationLevel, -1);
        assert.equal(searchData.location_name, '');
    });

    it('tests moveToLocation not national', function () {
        controller.moveToLocation({location_id: 'test-id', name: 'name'}, 3);

        var searchData = $location.search();

        assert.equal(searchData.location_id, 'test-id');
        assert.equal(searchData.selectedLocationLevel, 3);
        assert.equal(searchData.location_name, 'name');
    });

    it('tests disable locations for user', function () {
        controller.userLocationId = 'test_id4';
        controller.location = {name: 'name4', location_id: 'test_id4'};
        controller.selectedLocations.push(
            {name: 'name1', location_id: 'test_id1'},
            {name: 'name2', location_id: 'test_id2'},
            {name: 'name3', location_id: 'test_id3'},
            {name: 'name4', location_id: 'test_id4'},
            {name: 'name5', location_id: 'test_id5'},
            {name: 'name6', location_id: 'test_id6'}
        );
        var index = controller.getDisableIndex();
        assert.equal(index, 3);
    });
});
