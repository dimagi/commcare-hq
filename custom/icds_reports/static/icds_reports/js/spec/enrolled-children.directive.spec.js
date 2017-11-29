/* global module, inject, _ */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('EnrolledChildrenDirective', function () {

    var $scope, $httpBackend, $location, controller;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('enrolled_children', 'enrolled_children');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("genders", [
            {id: '', name: 'All'},
            {id: 'M', name: 'Male'},
            {id: 'F', name: 'Female'},
        ]);
        $provide.constant('ages', [
            {id: '', name: 'All'},
            {id: '6', name: '0-6 months'},
            {id: '12', name: '6-12 months'},
            {id: '24', name: '12-24 months'},
            {id: '36', name: '24-36 months'},
            {id: '48', name: '36-48 months'},
            {id: '60', name: '48-60 months'},
            {id: '72', name: '60-72 months'},
        ]);
        $provide.constant("userLocationId", null);
    }));

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('enrolled_children').respond(200, {
            report_data: ['report_test_data'],
        });
        var element = window.angular.element("<enrolled-children data='test'></enrolled-children>");
        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('enrolledChildren');
        controller.step = 'map';
    }));


    it('tests initial state', function () {
        assert.equal(controller.mode, 'map');
        assert.equal(controller.steps['map'].label, 'Map View: National');
        assert.deepEqual(controller.filtersData, {});
    });

    it('tests supervisor location', function () {
        controller.filtersData.location_id = 'test-id';

        $httpBackend.expectGET('icds_locations?location_id=test-id').respond(200, {location_type: 'supervisor'});
        $httpBackend.expectGET('enrolled_children?location_id=test-id').respond(200, {
            report_data: ['report_test_data'],
        });
        controller.init();
        $httpBackend.flush();
        assert.equal(controller.mode, 'sector');
        assert.equal(controller.steps['map'].label, 'Sector View');
        assert.deepEqual(controller.data.mapData, ['report_test_data']);
    });

    it('tests non supervisor location', function () {
        controller.filtersData.location_id = 'test-id';

        $httpBackend.expectGET('icds_locations?location_id=test-id').respond(200, {location_type: 'non supervisor'});
        $httpBackend.expectGET('enrolled_children?location_id=test-id').respond(200, {
            report_data: ['report_test_data'],
        });
        controller.init();
        $httpBackend.flush();
        assert.equal(controller.mode, 'map');
        assert.equal(controller.steps['map'].label, 'Map View: Non supervisor');
        assert.deepEqual(controller.data.mapData, ['report_test_data']);
    });

    it('tests template popup', function () {
        var result = controller.templatePopup({properties: {name: 'test'}}, {valid: 2, all: 4});
        var expected = '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>test</p>' +
            '<div>Number of children (0 - 6 years) who are enrolled for ICDS services: <strong>2</strong>' +
            '<div>Total number of children (0 - 6 years) who are registered: <strong>3</strong>' +
            '<div>Percentage of registered children (0-6 years) who are enrolled for ICDS services: <strong>50.00%</strong>' +
            '</div>';
        assert.equal(result, expected);

    it('tests location change', function () {
        controller.init();
        controller.selectedLocations.push(
            {name: 'name1', location_id: 'test_id1'},
            {name: 'name2', location_id: 'test_id2'},
            {name: 'name3', location_id: 'test_id3'},
            {name: 'name4', location_id: 'test_id4'},
            {name: 'name5', location_id: 'test_id5'},
            {name: 'name6', location_id: 'test_id6'}
        );
        $httpBackend.expectGET('enrolled_children').respond(200, {
            report_data: ['report_test_data'],
        });
        $scope.$digest();
        $httpBackend.flush();
        assert.equal($location.search().location_id, 'test_id4');
        assert.equal($location.search().selectedLocationLevel, 3);
        assert.equal($location.search().location_name, 'name4');
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

    it('tests show all locations', function () {
        controller.all_locations.push(
            {name: 'name1', location_id: 'test_id1'}
        );
        var locations = controller.showAllLocations();
        assert.equal(locations, true);
    });

    it('tests not show all locations', function () {
        controller.all_locations.push(
            {name: 'name1', location_id: 'test_id1'},
            {name: 'name2', location_id: 'test_id2'},
            {name: 'name3', location_id: 'test_id3'},
            {name: 'name4', location_id: 'test_id4'},
            {name: 'name5', location_id: 'test_id5'},
            {name: 'name6', location_id: 'test_id6'},
            {name: 'name7', location_id: 'test_id7'},
            {name: 'name8', location_id: 'test_id8'},
            {name: 'name9', location_id: 'test_id9'},
            {name: 'name10', location_id: 'test_id10'}
        );
        var locations = controller.showAllLocations();
        assert.equal(locations, false);
    });

    it('tests chart options', function () {
        var chart = controller.chartOptions.chart;
        var caption = controller.chartOptions.caption;
        assert.notEqual(chart, null);
        assert.notEqual(caption, null);
        assert.equal(controller.chartOptions.chart.type, 'multiBarChart');
        assert.deepEqual(controller.chartOptions.chart.margin, {
            top: 20,
            right: 60,
            bottom: 60,
            left: 80,
        });
        assert.equal(controller.chartOptions.chart.clipVoronoi, false);
        assert.equal(controller.chartOptions.chart.xAxis.axisLabel, '');
        assert.equal(controller.chartOptions.chart.xAxis.showMaxMin, true);
        assert.equal(controller.chartOptions.chart.yAxis.axisLabel, '');
        assert.equal(controller.chartOptions.caption.enable, true);
        assert.deepEqual(controller.chartOptions.caption.css, {
            'text-align': 'center',
            'margin': '0 auto',
            'width': '900px',
        });
        assert.equal(controller.chartOptions.caption.html,
            '<i class="fa fa-info-circle"></i> ' +
            'Total number of children between the age of 0 - 6 years who are enrolled for ICDS services'
        );
    });

    it('tests chart tooltip content', function () {
        var data = {y: 0.5, all: 2};
        var x = 'test age';
        var expected = "<p>Total number of children between the age of 0 - 6 years who are enrolled for ICDS services: <strong>2</strong></p>"
            + "<p>% of children test age: <strong>25.00%</strong></p>";

        var result = controller.tooltipContent(data, x);
        assert.equal(expected, result);
    });

    it('tests reset additional filters', function () {
        controller.filtersData.gender = 'test';
        controller.filtersData.age = 'test';
        controller.resetAdditionalFilter();

        assert.equal(controller.filtersData.gender, null);
        assert.equal(controller.filtersData.age, null);
    });

    it('tests reset only age additional filters', function () {
        controller.filtersData.gender = 'test';

        controller.resetOnlyAgeAdditionalFilter();
        assert.equal(controller.filtersData.gender, 'test');
        assert.equal(controller.filtersData.age, null);
    });
});
