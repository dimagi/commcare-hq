/* global module, inject, _, chai */
"use strict";

var utils = hqImport('icds_reports/js/spec/utils');
var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Immunization Coverage Directive', function () {

    var $scope, $httpBackend, $location, controller, controllermapOrSectorView;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('immunization_coverage', 'immunization_coverage');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        utils.provideDefaultConstants($provide, {includeGenders: true});
    }));

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('immunization_coverage').respond(200, {
            report_data: ['report_test_data'],
        });
        $httpBackend.expectGET('icds_locations').respond(200, {
            location_type: 'state',
        });
        var element = window.angular.element("<immunization-coverage data='test'></immunization-coverage>");
        var compiled = $compile(element)($scope);
        var mapOrSectorViewElement = window.angular.element("<map-or-sector-view data='test'></map-or-sector-view>");
        var mapOrSectorViewCompiled = $compile(mapOrSectorViewElement)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('immunizationCoverage');
        controller.step = 'map';
        controllermapOrSectorView = mapOrSectorViewCompiled.controller('mapOrSectorView');
        controllermapOrSectorView.data = _.clone(utils.controllerMapOrSectorViewData);
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests initial state', function () {
        assert.equal(controller.mode, 'map');
        assert.equal(controller.steps['map'].label, 'Map View: National');
        assert.deepEqual(controller.filtersData, {});
    });

    it('tests supervisor location', function () {
        controller.filtersData.location_id = 'test-id';
        controller.userLocationId = 'test-id';

        $httpBackend.expectGET('icds_locations?location_id=test-id').respond(200, {location_type: 'supervisor'});
        $httpBackend.expectGET('immunization_coverage?location_id=test-id').respond(200, {
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
        controller.userLocationId = 'test-id';

        $httpBackend.expectGET('icds_locations?location_id=test-id').respond(200, {location_type: 'non supervisor'});
        $httpBackend.expectGET('immunization_coverage?location_id=test-id').respond(200, {
            report_data: ['report_test_data'],
        });
        controller.init();
        $httpBackend.flush();
        assert.equal(controller.mode, 'map');
        assert.equal(controller.steps['map'].label, 'Map View: Non supervisor');
        assert.deepEqual(controller.data.mapData, ['report_test_data']);
    });

    it('tests template popup', function () {
        var result = controller.templatePopup({properties: {name: 'test'}}, {all: 10, children: 5});
        assert.equal(result, '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>test</p>'
            + '<div>Total number of ICDS Child beneficiaries between 1-2 years old: <strong>10</strong></div>'
            + '<div>Total number of children between 1-2 years old who have received complete immunizations required by age 1: <strong>5</strong></div>'
            + '<div>% of children between 1-2 years old who have received complete immunizations required by age 1: <strong>50.00%</strong></div></div>');
    });

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
        $httpBackend.expectGET('immunization_coverage').respond(200, {
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

    it('tests chart options', function () {
        var chart = controller.chartOptions.chart;
        var caption = controller.chartOptions.caption;
        assert.notEqual(chart, null);
        assert.notEqual(caption, null);
        assert.equal(controller.chartOptions.chart.type, 'lineChart');
        assert.deepEqual(controller.chartOptions.chart.margin, {
            top: 20,
            right: 60,
            bottom: 60,
            left: 80,
        });
        assert.equal(controller.chartOptions.chart.clipVoronoi, false);
        assert.equal(controller.chartOptions.chart.tooltips, true);
        assert.equal(controller.chartOptions.chart.xAxis.axisLabel, '');
        assert.equal(controller.chartOptions.chart.xAxis.showMaxMin, true);
        assert.equal(controller.chartOptions.chart.xAxis.axisLabelDistance, -100);
        assert.equal(controller.chartOptions.chart.yAxis.axisLabel, '');
        assert.equal(controller.chartOptions.chart.yAxis.axisLabelDistance, 20);
        assert.equal(controller.chartOptions.caption.enable, true);
        assert.deepEqual(controller.chartOptions.caption.css, {
            'text-align': 'center',
            'margin': '0 auto',
            'width': '900px',
        });
        assert.equal(controller.chartOptions.caption.html,
            '<i class="fa fa-info-circle"></i> '
            + 'Of the total number of children enrolled for Anganwadi Services who are between 1-2 years old, the percentage of children who have received the complete immunization as per the National Immunization Schedule of India that is required by age 1. <br/><br/>'
            + 'This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1'
            + '<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1');
    });

    it('tests chart tooltip content', function () {
        var data = {in_month: 5, y: 0.72, all: 10};
        var month = {value: "Jul 2017", series: []};

        var expected = '<p><strong>Jul 2017</strong></p><br/>'
            + '<div>Total number of ICDS Child beneficiaries between 1-2 years old: <strong>10</strong></div>'
            + '<div>Total number of children between 1-2 years old who have received complete immunizations required by age 1: <strong>5</strong></div>'
            + '<div>% of children between 1-2 years old who have received complete immunizations required by age 1: <strong>72.00%</strong></div>';

        var result = controller.tooltipContent(month.value, data);
        assert.equal(expected, result);
    });

    it('tests horizontal chart tooltip content', function () {
        var expected = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>Ambah</p>' +
            '<div>Total number of ICDS Child beneficiaries between 1-2 years old: <strong>25</strong></div>' +
            '<div>Total number of children between 1-2 years old who have received complete immunizations required by age 1: <strong>0</strong></div>' +
            '<div>% of children between 1-2 years old who have received complete immunizations required by age 1: <strong>NaN%</strong></div></div>';
        controllermapOrSectorView.templatePopup = function (d) {
            return controller.templatePopup(d.loc, d.row);
        };
        var result = controllermapOrSectorView.chartOptions.chart.tooltip.contentGenerator(utils.d);
        assert.equal(expected, result);
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

    it('tests reset additional filters', function () {
        controller.filtersData.gender = 'test';
        controller.resetAdditionalFilter();

        assert.equal(controller.filtersData.gender, null);
    });


});

describe('Immunization Coverage Directive 1-2 years', function () {

    var $scope, $httpBackend, $location, controller, controllermapOrSectorView;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('immunization_coverage', 'immunization_coverage');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        utils.provideDefaultConstants($provide, {includeGenders: true});
        $provide.constant("haveAccessToFeatures", false);

    }));


    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('immunization_coverage').respond(200, {
            report_data: ['report_test_data'],
        });
        $httpBackend.expectGET('icds_locations').respond(200, {
            location_type: 'state',
        });
        var element = window.angular.element("<immunization-coverage data='test'></immunization-coverage>");
        var compiled = $compile(element)($scope);
        var mapOrSectorViewElement = window.angular.element("<map-or-sector-view data='test'></map-or-sector-view>");
        var mapOrSectorViewCompiled = $compile(mapOrSectorViewElement)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('immunizationCoverage');
        controller.step = 'map';
        controllermapOrSectorView = mapOrSectorViewCompiled.controller('mapOrSectorView');
        controllermapOrSectorView.data = _.clone(utils.controllerMapOrSectorViewData);
    }));

    it('tests template popup', function () {
        var result = controller.templatePopup({properties: {name: 'test'}}, {all: 10, children: 5});
        var expected = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>test</p>'
            + '<div>Total number of ICDS Child beneficiaries between 1-2 years old: <strong>10</strong></div>'
            + '<div>Total number of children between 1-2 years old who have received complete immunizations required by age 1: <strong>5</strong></div>'
            + '<div>% of children between 1-2 years old who have received complete immunizations required by age 1: <strong>50.00%</strong></div></div>';
        assert.equal(result, expected);
    });

    it('tests chart options', function () {
        var chart = controller.chartOptions.chart;
        var caption = controller.chartOptions.caption;
        assert.notEqual(chart, null);
        assert.notEqual(caption, null);
        assert.equal(controller.chartOptions.chart.type, 'lineChart');
        assert.deepEqual(controller.chartOptions.chart.margin, {
            top: 20,
            right: 60,
            bottom: 60,
            left: 80,
        });
        assert.equal(controller.chartOptions.chart.clipVoronoi, false);
        assert.equal(controller.chartOptions.chart.tooltips, true);
        assert.equal(controller.chartOptions.chart.xAxis.axisLabel, '');
        assert.equal(controller.chartOptions.chart.xAxis.showMaxMin, true);
        assert.equal(controller.chartOptions.chart.xAxis.axisLabelDistance, -100);
        assert.equal(controller.chartOptions.chart.yAxis.axisLabel, '');
        assert.equal(controller.chartOptions.chart.yAxis.axisLabelDistance, 20);
        assert.equal(controller.chartOptions.caption.enable, true);
        assert.deepEqual(controller.chartOptions.caption.css, {
            'text-align': 'center',
            'margin': '0 auto',
            'width': '900px',
        });
        var expected = '<i class="fa fa-info-circle"></i> '
            + 'Of the total number of children enrolled for Anganwadi Services who are between 1-2 years old, the percentage of children who have received the complete immunization as per the National Immunization Schedule of India that is required by age 1. <br/><br/>'
            + 'This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1'
            + '<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1';
        assert.equal(controller.chartOptions.caption.html, expected);
    });

    it('tests chart tooltip content', function () {
        var data = {in_month: 5, y: 0.72, all: 10};
        var month = {value: "Jul 2017", series: []};

        var expected = '<p><strong>Jul 2017</strong></p><br/>'
            + '<div>Total number of ICDS Child beneficiaries between 1-2 years old: <strong>10</strong></div>'
            + '<div>Total number of children between 1-2 years old who have received complete immunizations required by age 1: <strong>5</strong></div>'
            + '<div>% of children between 1-2 years old who have received complete immunizations required by age 1: <strong>72.00%</strong></div>';

        var result = controller.tooltipContent(month.value, data);
        assert.equal(expected, result);
    });

    it('tests horizontal chart tooltip content', function () {
        var expected = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>Ambah</p>' +
            '<div>Total number of ICDS Child beneficiaries between 1-2 years old: <strong>25</strong></div>' +
            '<div>Total number of children between 1-2 years old who have received complete immunizations required by age 1: <strong>0</strong></div>' +
            '<div>% of children between 1-2 years old who have received complete immunizations required by age 1: <strong>NaN%</strong></div></div>';
        controllermapOrSectorView.templatePopup = function (d) {
            return controller.templatePopup(d.loc, d.row);
        };
        var result = controllermapOrSectorView.chartOptions.chart.tooltip.contentGenerator(utils.d);
        assert.equal(expected, result);
    });

});
