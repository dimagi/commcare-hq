"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('AdolescentGirlsDirective', function () {

    var $scope, $httpBackend, $location, controller;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('adolescent_girls', 'adolescent_girls');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function($provide) {
        $provide.constant("userLocationId", null);
    }));

    beforeEach(inject(function($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;
        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('adolescent_girls').respond(200, {
            report_data: [],
        });
        var element = window.angular.element("<adolescent-girls data='test'></adolescent-girls>");
        var compiled = $compile(element)($scope);
        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('adolescentGirls');
        controller.step = 'map';
    }));

    it('tests initial state', function() {
        assert.equal(controller.mode, 'map');
        assert.equal(controller.steps['map'].label, 'Map View: National');
        assert.deepEqual(controller.filtersData, {});
    });

    it('tests supervisor location', function() {
        controller.filtersData.location_id = 'test-id';

        $httpBackend.expectGET('icds_locations?location_id=test-id').respond(200, {location_type: 'supervisor'});
        $httpBackend.expectGET('adolescent_girls?location_id=test-id').respond(200, {
            report_data: [],
        });
        controller.init();
        $httpBackend.flush();
        assert.equal(controller.mode, 'sector');
        assert.equal(controller.steps['map'].label, 'Sector View');
        assert.deepEqual(controller.data.mapData, []);
    });

    it('tests location change', function () {
        controller.init();
        controller.selectedLocations.push(
            {location_id: 'test_id'},
            {location_id: 'test_id2'},
            {location_id: 'test_id3'},
            {location_id: 'test_id4'},
            {location_id: 'test_id5'},
            {location_id: 'test_id6'}
        );
        $httpBackend.expectGET('adolescent_girls').respond(200, {
            report_data: [],
        });
        $scope.$digest();
        $httpBackend.flush();
        assert.equal($location.search().location_id, 'test_id4');
    });

    it('tests template popup', function () {
        var result = controller.templatePopup({properties: {name: 'test'}}, {valid: 14});
        assert.equal(result, '<div class="hoverinfo" style="max-width: 200px !important;"><p>test</p><div>Total number of adolescent girls who are enrolled for ICDS services: <strong>14</strong></div>');
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
});
