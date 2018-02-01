/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('AWC Reports Directive', function () {

    var $scope, $httpBackend, $location, controller;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('awc_reports', 'awc_reports');
    pageData.registerUrl('icds_locations', 'icds_locations');
    pageData.registerUrl('awc_reports', 'beneficiary_details');

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
    }));

    var mockBeneficiaryDetails = {
        "age_in_months": 43,
        'weight': [{'x': 5, 'y': 10}, {'x': 10, 'y': 15}, {'x': 15, 'y': 20}, {'x': 20, 'y': 25}],
        'wfl': [{'x': 105, 'y': 10}, {'x': 110, 'y': 15}, {'x': 115, 'y': 20}, {'x': 120, 'y': 25}],
        "dob": "2014-03-15",
        "age": "3 years 8 months ",
        "height": [{'x': 5, 'y': 105}, {'x': 10, 'y': 110}, {'x': 15, 'y': 115}, {'x': 20, 'y': 120}],
        "person_name": "child1HH1-05",
        "sex": "M",
        "mother_name": "motherHH1",
    };

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');

        var element = window.angular.element("<awc-reports data='test'></awc-reports>");
        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('awcReports');
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests show info message', function () {
        var fakeDate = new Date(2016, 1, 1);
        var clock = sinon.useFakeTimers(fakeDate.getTime());

        var expected = true;
        var result = controller.showInfoMessage();

        assert.equal(expected, result);
        clock.restore();
    });

    it('tests show info message for second day also', function () {
        var fakeDate = new Date(2016, 1, 2);
        var clock = sinon.useFakeTimers(fakeDate.getTime());

        var expected = true;
        var result = controller.showInfoMessage();

        assert.equal(expected, result);
        clock.restore();
    });

    it('tests not show info message', function () {
        var fakeDate = new Date(2016, 1, 3);
        var clock = sinon.useFakeTimers(fakeDate.getTime());

        var expected = false;
        var result = controller.showInfoMessage();

        assert.equal(expected, result);
        clock.restore();
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

    it('tests show beneficiary table', function () {
        controller.showBeneficiaryTable();

        assert.deepEqual(controller.filters, ['gender']);
        assert.equal(controller.beneficiary, null);
        assert.equal(controller.showBeneficiary, false);
        assert.equal(controller.showTable, true);
    });

    it('tests get popover content', function () {
        var expected = "<div>Weight: 50.00 kg</div><div>Height: 150.00 cm</div><div>Age: 40 months</div>";
        var result = controller.getPopoverContent(50, 150, 40, 'both');
        assert.equal(expected, result);
    });

    it('tests chart options', function () {
        var chart = controller.chartOptions.chart;
        assert.notEqual(chart, null);
        assert.equal(chart.type, 'multiBarChart');
        assert.equal(chart.height, 450);
        assert.equal(chart.width, 1100);
        assert.deepEqual(chart.margin, {
            top: 20,
            right: 20,
            bottom: 50,
            left: 80,
        });
        assert.equal(chart.showValues, true);
        assert.equal(chart.showControls, false);
        assert.equal(chart.duration, 500);
        assert.equal(chart.clipVoronoi, false);
        assert.equal(chart.useInteractiveGuideline, true);
        assert.equal(chart.xAxis.axisLabel, '');
        assert.equal(chart.yAxis.axisLabel, '');
    });

    it('tests line chart days per week options', function () {
        var chart = controller.lineChartDaysPerWeekOptions.chart;
        assert.notEqual(chart, null);
        assert.equal(chart.type, 'multiBarChart');
        assert.equal(chart.height, 450);
        assert.equal(chart.width, 1100);
        assert.deepEqual(chart.margin, {
            top: 20,
            right: 20,
            bottom: 150,
            left: 80,
        });
        assert.equal(chart.showValues, true);
        assert.equal(chart.showLegend, false);
        assert.equal(chart.showControls, false);
        assert.equal(chart.duration, 500);
        assert.equal(chart.clipVoronoi, false);
        assert.equal(chart.useInteractiveGuideline, false);
        assert.equal(chart.xAxis.axisLabel, 'Week');
        assert.equal(chart.xAxis.staggerLabels, true);
        assert.equal(chart.xAxis.showMaxMin, false);
        assert.equal(chart.yAxis.axisLabel, 'Number of Days');
        assert.equal(chart.reduceXTicks, false);
        assert.equal(chart.staggerLabels, false);
    });

    it('tests line chart options', function () {
        var chart = controller.lineChartOptions.chart;
        assert.notEqual(chart, null);
        assert.equal(chart.type, 'lineChart');
        assert.equal(chart.height, 450);
        assert.equal(chart.width, 1100);
        assert.deepEqual(chart.margin, {
            top: 20,
            right: 50,
            bottom: 100,
            left: 80,
        });
        assert.equal(chart.showValues, true);
        assert.equal(chart.showLegend, false);
        assert.equal(chart.showControls, false);
        assert.equal(chart.duration, 1000);
        assert.equal(chart.clipVoronoi, false);
        assert.equal(chart.useInteractiveGuideline, true);
        assert.equal(chart.xAxis.axisLabel, 'Day');
        assert.equal(chart.xAxis.staggerLabels, true);
        assert.equal(chart.xAxis.showMaxMin, false);
        assert.equal(chart.yAxis.axisLabel, 'Number of Children');
        assert.equal(chart.reduceXTicks, false);
        assert.equal(chart.showLegend, false);
    });

    it('tests go to beneficiary details', function () {
        var expected = '/awc_reports/beneficiary_details';

        controller.goToBeneficiaryDetails('test');
        var result = $location.path();

        assert.equal(expected, result);
    });

    it('tests get data for step', function () {
        controller.filtersData.location_id = 'test-id';
        controller.selectedLocationLevel = 4;
        var step = 'beneficiary';
        var mockBeneficiaryDetails = {
            "age_in_months": 43, "weight": [50], "wfl": [], "dob": "2014-03-15",
            "age": "3 years 8 months ", "height": [150], "person_name": "child1HH1-05",
            "sex": "M", "mother_name": "motherHH1",
        };

        $httpBackend.expectGET('beneficiary_details?location_id=test-id').respond(200, mockBeneficiaryDetails);
        controller.getDataForStep(step);
        $httpBackend.flush();

        var centerExpected = {"lat": 22.1, "lng": 78.22, "zoom": 5};
        assert.deepEqual(controller.center, centerExpected);
        assert.equal(controller.message, false);
        assert.notEqual(controller.markers, null);
    });

    it('tests show beneficiary details', function () {
        this.timeout(500);
        controller.filtersData.location_id = 'test-id';

        $httpBackend.expectGET('beneficiary_details?location_id=test-id')
            .respond(200, mockBeneficiaryDetails);

        controller.showBeneficiaryDetails();
        $httpBackend.flush();

        assert.deepEqual(controller.lineChartOneData, mockBeneficiaryDetails.weight);
        assert.deepEqual(controller.lineChartTwoData, mockBeneficiaryDetails.height);
        assert.deepEqual(controller.lineChartThreeData, mockBeneficiaryDetails.wfl);
        assert.equal(controller.showBeneficiary, true);
        assert.equal(controller.showTable, false);

        assert.equal(controller.beneficiaryChartOneData.length, 4);
        assert.deepEqual(controller.beneficiaryChartOneData[3], {
            key: 'line',
            type: 'line',
            values: mockBeneficiaryDetails.weight,
            color: 'black',
            strokeWidth: 2,
            yAxis: 1,
        });
        assert.equal(controller.beneficiaryChartTwoData.length, 4);
        assert.deepEqual(controller.beneficiaryChartTwoData[3], {
            key: 'line',
            type: 'line',
            values: mockBeneficiaryDetails.height,
            color: 'black',
            yAxis: 1,
        });
        assert.equal(controller.beneficiaryChartThreeData.length, 4);
        assert.deepEqual(controller.beneficiaryChartThreeData[3], {
            key: 'line',
            type: 'line',
            values: mockBeneficiaryDetails.wfl,
            color: 'black',
            yAxis: 1,
        });
    });

    it('tests beneficiary chart options HFA', function () {
        var chart = controller.beneficiaryChartOptionsHFA.chart;
        assert.notEqual(chart, null);
        assert.equal(chart.type, 'lineChart');
        assert.equal(chart.height, 450);
        assert.deepEqual(chart.margin, {
            top: 20,
            right: 20,
            bottom: 50,
            left: 80,
        });
        assert.equal(chart.showControls, false);
        assert.equal(chart.duration, 100);
        assert.equal(chart.useInteractiveGuideline, true);
        assert.equal(chart.xAxis.axisLabel, 'Age (Months)');
        assert.deepEqual(chart.xAxis.tickValues, [0, 12, 24, 36, 48, 60]);
        assert.equal(chart.yAxis.axisLabel, 'Height (Cm)');
        assert.equal(chart.yAxis.rotateLabels, -90);
    });

    it('tests beneficiary chart options WFA', function () {
        var chart = controller.beneficiaryChartOptionsWFA.chart;
        assert.notEqual(chart, null);
        assert.equal(chart.type, 'lineChart');
        assert.equal(chart.height, 450);
        assert.deepEqual(chart.margin, {
            top: 20,
            right: 20,
            bottom: 50,
            left: 80,
        });
        assert.equal(chart.showControls, false);
        assert.equal(chart.duration, 100);
        assert.equal(chart.useInteractiveGuideline, true);
        assert.equal(chart.xAxis.axisLabel, 'Age (Months)');
        assert.deepEqual(chart.xAxis.tickValues, [0, 12, 24, 36, 48, 60]);
        assert.equal(chart.yAxis.axisLabel, 'Weight (Kg)');
        assert.equal(chart.yAxis.rotateLabels, -90);
    });

    it('tests beneficiary chart options WFH', function () {
        var chart = controller.beneficiaryChartOptionsWFH.chart;
        assert.notEqual(chart, null);
        assert.equal(chart.type, 'lineChart');
        assert.equal(chart.height, 450);
        assert.deepEqual(chart.margin, {
            top: 20,
            right: 20,
            bottom: 50,
            left: 80,
        });
        assert.equal(chart.showControls, false);
        assert.equal(chart.duration, 100);
        assert.equal(chart.useInteractiveGuideline, true);
        assert.equal(chart.xAxis.axisLabel, 'Height (Cm)');
        assert.deepEqual(chart.xDomain, [45, 120]);
        assert.equal(chart.yAxis.axisLabel, 'Weight (Kg)');
        assert.equal(chart.yAxis.rotateLabels, -90);
    });
});