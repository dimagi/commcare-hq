/* global module, inject, chai, Datamap, STATES_TOPOJSON, DISTRICT_TOPOJSON, BLOCK_TOPOJSON */
"use strict";

var utils = hqImport('icds_reports/js/spec/utils');
var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('Indie Map Directive', function () {
    this.timeout(10000);  // bump timeout for maps tests because they are slow...

    var $scope, $location, controller, $httpBackend, $storageService;

    pageData.registerUrl('icds_locations', 'icds_locations');
    pageData.registerUrl('icds-ng-template', 'template');

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
        utils.provideDefaultConstants($provide, {});
        $provide.constant('haveAccessToFeatures', false);

    }));

    beforeEach(inject(function ($rootScope, _$compile_, _$location_, _$httpBackend_, storageService) {
        $scope = $rootScope.$new();
        $location = _$location_;
        $httpBackend = _$httpBackend_;
        $storageService = storageService;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('icds_locations').respond(200, mockLocation);
        $httpBackend.expectGET('/static/js/topojsons/states_v4.topojson').respond(200, '');

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
        // topojson comparisons temporarily commented out until I can figure out how to test
        // them again.
        // assert.equal(Datamap.prototype['indTopo'], STATES_TOPOJSON);
    });
    it('tests init topo json when location level equal -1', function () {
        $location.search('selectedLocationLevel', -1);
        var locationLevel = $location.search()['selectedLocationLevel'];
        assert.equal(locationLevel, -1);

        assert.equal(controller.scope, 'ind');
        assert.equal(controller.type, 'indTopo');
        // assert.equal(Datamap.prototype['indTopo'], STATES_TOPOJSON);
    });

    it('tests init topo json when location level equal 4', function () {
        $location.search('selectedLocationLevel', 4);
        var locationLevel = $location.search()['selectedLocationLevel'];
        assert.equal(locationLevel, 4);

        assert.equal(controller.scope, 'ind');
        assert.equal(controller.type, 'indTopo');
        // assert.equal(Datamap.prototype['indTopo'], STATES_TOPOJSON);
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
        // assert.equal(Datamap.prototype['Madhya PradeshTopo'], DISTRICT_TOPOJSON);
    });

    it('tests init topo json when location level equal 1', function () {
        $location.search('selectedLocationLevel', 1);
        $location.search('location_name', 'Anantapur');

        var locationLevel = $location.search()['selectedLocationLevel'];
        var location = {
            location_type: "district",
            location_type_name: "district",
            map_location_name: "Anantapur",
            name: "Anantapur",
        };

        assert.equal(locationLevel, 1);
        assert.equal(location.name, 'Anantapur');

        controller.initTopoJson(locationLevel, location);

        assert.equal(controller.scope, 'Anantapur');
        assert.equal(controller.type, 'AnantapurTopo');
        // assert.equal(Datamap.prototype['AnantapurTopo'], BLOCK_TOPOJSON);
    });

    it('tests html content of update map', function () {
        controller.data = mockData;
        var expected = '<div class="secondary-location-selector">' +
            '<div class="modal-header"><button type="button" class="close" ' +
            'ng-click="$ctrl.closePopup($event)" aria-label="Close"><span aria-hidden="true">&times;</span>' +
            '</button></div><div class="modal-body"><button class="btn btn-xs btn-default" ' +
            'ng-click="$ctrl.attemptToDrillToLocation(\'Uttar Pradesh\')">Uttar Pradesh</button>' +
            '</div></div>';

        var result = controller.getSecondaryLocationSelectionHtml(mockGeography);
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
        controller.handleMapClick(mockGeography);
        $httpBackend.flush();

        expected = {"location_id": "9951736acfe54c68948225cc05fbbd63", "location_name": "Chhattisgarh"};
        result = $location.search();

        assert.deepEqual(expected, result);
        assert.deepEqual($storageService.getKey('search'), expected);
    });
});
