/* global module, inject, _, chai */
"use strict";

var utils = hqImport('icds_reports/js/spec/utils');
var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Early Initiation Breastfeeding Directive', function () {

    var $scope, $httpBackend, $location, controller, controllermapOrSectorView;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('early_initiation', 'early_initiation');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        utils.provideDefaultConstants($provide, {includeGenders: true});
    }));

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        $httpBackend.expectGET('early_initiation').respond(200, {
            report_data: ['report_test_data'],
        });
        $httpBackend.expectGET('icds_locations').respond(200, {
            location_type: 'state',
        });
        $scope.test = {};
        var element = window.angular.element("<early-initiation-breastfeeding></early-initiation-breastfeeding>");
        var compiled = $compile(element)($scope);
        var mapOrSectorViewElement = window.angular.element("<map-or-sector-view data='test'></map-or-sector-view>");
        var mapOrSectorViewCompiled = $compile(mapOrSectorViewElement)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('earlyInitiationBreastfeeding');
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
        $httpBackend.expectGET('early_initiation?location_id=test-id').respond(200, {
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
        $httpBackend.expectGET('early_initiation?location_id=test-id').respond(200, {
            report_data: ['report_test_data'],
        });
        controller.init();
        $httpBackend.flush();
        assert.equal(controller.mode, 'map');
        assert.equal(controller.steps['map'].label, 'Map View: Non supervisor');
        assert.deepEqual(controller.data.mapData, ['report_test_data']);
    });

    it('tests template popup', function () {
        var result = controller.templatePopup({properties: {name: 'test'}}, {in_month: 10, birth: 5});
        assert.equal(result, '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">'
            + '<p>test</p>'
            + '<div>Total Number of Children born in the current month: <strong>10</strong></div>'
            + '<div>Total Number of Children who were put to the breast within one hour of birth: <strong>5</strong></div>'
            + '<div>% children who were put to the breast within one hour of birth: <strong>50.00%</strong></div></div>');
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
        $httpBackend.expectGET('early_initiation').respond(200, {
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
            '<i class="fa fa-info-circle"></i> ' +
            'Of the children born in the given month and enrolled for Anganwadi services, the percentage whose breastfeeding was initiated within 1 hour of delivery. \n' +
            '\n' +
            'Early initiation of breastfeeding ensure the newborn recieves the "first milk" rich in nutrients and encourages exclusive breastfeeding practice'
        );
    });

    it('tests chart tooltip content', function () {
        var data = {y: 0.2434, birth: 5, all: 171};
        var month = {value: "Jul 2017", series: []};

        var expected = '<p><strong>Jul 2017</strong></p><br/>'
            + '<div>Total Number of Children born in the given month: <strong>171</strong></div>'
            + '<div>Total Number of Children who were put to the breast within one hour of birth: <strong>5</strong></div>'
            + '<div>% children who were put to the breast within one hour of birth: <strong>24.34%</strong></div>';

        var result = controller.tooltipContent(month.value, data);
        assert.equal(expected, result);
    });

    it('tests horizontal chart tooltip content', function () {
        var expected = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>Ambah</p>' +
            '<div>Total Number of Children born in the current month: <strong>0</strong></div>' +
            '<div>Total Number of Children who were put to the breast within one hour of birth: <strong>0</strong></div>' +
            '<div>% children who were put to the breast within one hour of birth: <strong>NaN%</strong></div></div>';
        controllermapOrSectorView.templatePopup = function (d) {
            return controller.templatePopup(d.loc, d.row);
        };
        var result = controllermapOrSectorView.chartOptions.chart.tooltip.contentGenerator(utils.d);
        assert.equal(expected, result);
    });

    it('tests reset additional filters', function () {
        controller.filtersData.gender = 'test';
        controller.resetAdditionalFilter();

        assert.equal(controller.filtersData.gender, null);
    });
});
