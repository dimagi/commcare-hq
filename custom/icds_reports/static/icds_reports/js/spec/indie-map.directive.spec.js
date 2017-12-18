/* global module, inject, chai, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */
"use strict";

describe('Indie Map Directive', function () {

    var $scope, $location, controller, $httpBackend, $storageService;

    pageData.registerUrl('icds_locations', 'icds_locations');

    var mockGeography = {
        geometry: {type: "Polygon", coordinates: []},
        id: "test-id",
        properties: {STATE_CODE: "09", name: "Uttar Pradesh"},
        type: "Feature",
    };

    var mockData = [{
        data: {'test-id': {in_month: 0, original_name: ['Uttar Pradesh'], birth: 0, fillKey: "0%-20%"}},
    }];

    var mockFakeData = [{
        data: {'test-id': {in_month: 0, original_name: [], birth: 0, fillKey: "0%-20%"}},
    }];

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
        }]
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
        $location.search('location_name', 'test');

        var locationLevel = $location.search()['selectedLocationLevel'];
        var location = $location.search()['location_name'];

        assert.equal(locationLevel, 0);
        assert.equal(location, 'test');

        controller.initTopoJson(locationLevel, location);

        assert.equal(controller.scope, 'test');
        assert.equal(controller.type, 'testTopo');
        assert.equal(Datamap.prototype['testTopo'], DISTRICT_TOPOJSON);
    });

    it('tests init topo json when location level equal 1', function () {
        $location.search('selectedLocationLevel', 1);
        $location.search('location_name', 'test');

        var locationLevel = $location.search()['selectedLocationLevel'];
        var location = $location.search()['location_name'];

        assert.equal(locationLevel, 1);
        assert.equal(location, 'test');

        controller.initTopoJson(locationLevel, location);

        assert.equal(controller.scope, 'test');
        assert.equal(controller.type, 'testTopo');
        assert.equal(Datamap.prototype['testTopo'], BLOCK_TOPOJSON);
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
            "location_id": null
        });

        $httpBackend.expectGET('icds_locations?name=test-id').respond(200, mockLocations);
        controller.updateMap(mockGeography);
        $httpBackend.flush();

        expected = {"location_id": "9951736acfe54c68948225cc05fbbd63", "location_name": "test-id"};
        result = $location.search();

        assert.deepEqual(expected, result);
        assert.deepEqual($storageService.getKey('search'), {
            "location_name": "test-id", "location_id": "9951736acfe54c68948225cc05fbbd63"
        });
    });
});