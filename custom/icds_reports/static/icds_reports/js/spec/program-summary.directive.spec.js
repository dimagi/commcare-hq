/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('Program Summary Directive', function () {

    var $scope, $httpBackend, $location, controller;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('program_summary', 'program_summary');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        utils.provideDefaultConstants($provide, {});
        $provide.constant("navMetadata", {
            maternal_child: { 'label': 'Maternal and Child Nutrition' },
            icds_cas_reach: { 'label': 'ICDS-CAS Reach' },
            demographics: { 'label': 'Demographics' },
            awc_infrastructure: { 'label': 'AWC Infrastructure' },
        });
        $provide.constant("navMenuItems", {
            sections: [
                {'name': 'Maternal and Child Nutrition'},
                {'name': 'ICDS-CAS Reach'},
                {'name': 'Demographics'},
                {'name': 'AWC Infrastructure'},
            ],
        });
    }));

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('program_summary').respond(200, {
            report_data: ['report_test_data'],
        });
        var element = window.angular.element("<program-summary data='test'></program-summary>");
        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('programSummary');
        controller.step = 'maternal_child';
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

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
            {name: 'name1', location_id: 'test_id1', user_have_access: 0},
            {name: 'name2', location_id: 'test_id2', user_have_access: 0},
            {name: 'name3', location_id: 'test_id3', user_have_access: 0},
            {name: 'name4', location_id: 'test_id4', user_have_access: 1},
            {name: 'All', location_id: 'all', user_have_access: 0},
            null
        );
        var index = controller.getDisableIndex();
        assert.equal(index, 2);
    });
});
