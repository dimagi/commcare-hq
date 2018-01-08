/* global module, inject, chai, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('Indie Map Directive', function () {

    var $scope, $location, controller, $httpBackend, $storageService;

    pageData.registerUrl('icds_locations', 'icds_locations');

    var mockGeography = {
        geometry: {type: "Polygon", coordinates: []},
        id: "test-id",
        properties: {STATE_CODE: "09", name: "Uttar Pradesh"},
        type: "Feature",
    };

    var mockData = {
        data: {'test-id': {in_month: 0, original_name: ['Uttar Pradesh'], birth: 0, fillKey: "0%-20%"}},
    };

    var mockFakeData = {
        data: {'test-id': {in_month: 0, original_name: [], birth: 0, fillKey: "0%-20%"}},
    };

    var mockLocation = {
        location_type_name: "state",
        parent_id: null,
        location_id: "9951736acfe54c68948225cc05fbbd63",
        name: "Chhattisgarh",
    };

    var mockLocations = {
        'locations': [{
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        }],
    };

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
    }));

    beforeEach(inject(function ($rootScope, _$compile_, _$location_, _$httpBackend_, storageService) {
        $scope = $rootScope.$new();
        $location = _$location_;
        $httpBackend = _$httpBackend_;
        $storageService = storageService;

        $httpBackend.expectGET('icds_locations').respond(200, mockLocation);

        var element = window.angular.element("<indie-map data='test'></indie-map>");
        var compiled = _$compile_(element)($scope);

        $httpBackend.flush();
        $scope.$digest();

        controller = compiled.controller('indieMap');
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests init topo json when location level not exist', function () {
        var locationLevel = $location.search()['selectedLocationLevel'];
        assert.equal(locationLevel, null);

        assert.equal(controller.scope, 'ind');
        assert.equal(controller.type, 'indTopo');
        assert.equal(Datamap.prototype['indTopo'], STATES_TOPOJSON);
    });

    it('tests init topo json when location level equal -1', function () {
        $location.search('selectedLocationLevel', -1);
        var locationLevel = $location.search()['selectedLocationLevel'];
        assert.equal(locationLevel, -1);

        assert.equal(controller.scope, 'ind');
        assert.equal(controller.type, 'indTopo');
        assert.equal(Datamap.prototype['indTopo'], STATES_TOPOJSON);
    });

    it('tests init topo json when location level equal 4', function () {
        $location.search('selectedLocationLevel', 4);
        var locationLevel = $location.search()['selectedLocationLevel'];
        assert.equal(locationLevel, 4);

        assert.equal(controller.scope, 'ind');
        assert.equal(controller.type, 'indTopo');
        assert.equal(Datamap.prototype['indTopo'], STATES_TOPOJSON);
    });

    it('tests init topo json when location level equal 0', function () {
        $location.search('selectedLocationLevel', 0);
        $location.search('location_name', 'Madhya Pradesh');

        var locationLevel = $location.search()['selectedLocationLevel'];
        var location = {
            location_type: "state",
            location_type_name: "state",
            map_location_name: "Madhya Pradesh",
            name: "Madhya Pradesh",
        };

        assert.equal(locationLevel, 0);
        assert.equal(location.name, 'Madhya Pradesh');

        controller.initTopoJson(locationLevel, location);

        assert.equal(controller.scope, 'Madhya Pradesh');
        assert.equal(controller.type, 'Madhya PradeshTopo');
        assert.equal(Datamap.prototype['Madhya PradeshTopo'], DISTRICT_TOPOJSON);
    });

    it('tests init topo json when location level equal 1', function () {
        $location.search('selectedLocationLevel', 1);
        $location.search('location_name', 'test');

        var locationLevel = $location.search()['selectedLocationLevel'];
        var location = {
            location_type: "state",
            location_type_name: "state",
            map_location_name: "test_on_map",
            name: "test",
        };

        assert.equal(locationLevel, 1);
        assert.equal(location.name, 'test');

        controller.initTopoJson(locationLevel, location);

        assert.equal(controller.scope, 'test_on_map');
        assert.equal(controller.type, 'test_on_mapTopo');
        assert.equal(Datamap.prototype['test_on_mapTopo'], BLOCK_TOPOJSON);
    });

    it('tests html content of update map', function () {
        controller.data = mockData;
        var expected = "<button class=\"btn btn-xs btn-default\" ng-click=\"$ctrl.updateMap('Uttar Pradesh')\">Uttar Pradesh</button>";

        var result = controller.getContent(mockGeography);
        assert.equal(expected, result);
    });

    it('tests update map', function () {
        controller.data = mockFakeData;

        var expected = {};
        var result = $location.search();

        assert.deepEqual(expected, result);
        assert.deepEqual($storageService.getKey('search'), {
            "location_id": null,
        });

        $httpBackend.expectGET('icds_locations?name=test-id').respond(200, mockLocations);
        controller.updateMap(mockGeography);
        $httpBackend.flush();

        expected = {"location_id": "9951736acfe54c68948225cc05fbbd63", "location_name": "test-id"};
        result = $location.search();

        assert.deepEqual(expected, result);
        assert.deepEqual($storageService.getKey('search'), {
            "location_name": "test-id", "location_id": "9951736acfe54c68948225cc05fbbd63",
        });
    });
});