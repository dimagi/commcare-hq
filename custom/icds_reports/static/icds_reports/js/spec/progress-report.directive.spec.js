/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('Progress Report Directive', function () {

    var $scope, $httpBackend, $location, controller;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
    }));

    beforeEach(inject(function ($rootScope, $compile, _$httpBackend_, _$location_) {
        $scope = $rootScope.$new();
        $httpBackend = _$httpBackend_;
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        var element = window.angular.element("<progress-report data='test'></progress-report>");
        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller('progressReport');
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests initial state', function () {
        assert.equal(controller.showWarning, true);
        assert.deepEqual(controller.filtersData, {});
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

    it('tests location change', function () {
        controller.loadData();
        controller.selectedLocations.push(
            {name: 'name1', location_id: 'test_id1'},
            {name: 'name2', location_id: 'test_id2'},
            {name: 'name3', location_id: 'test_id3'},
            {name: 'name4', location_id: 'test_id4'},
            {name: 'name5', location_id: 'test_id5'},
            {name: 'name6', location_id: 'test_id6'}
        );
        $scope.$digest();

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

    it('tests get black css', function () {
        var index = 0;
        var expected = 'black';

        var result = controller.getCSS(null, index, null);

        assert.equal(expected, result);
    });

    it('tests get color if index equal 0', function () {
        var index = 0;
        var data = [{'html': 'test'}, {'html': 'test1'}, {'html': 'test1'}];
        var expected = 'black';

        var result = controller.getCSS(data, index, false);

        assert.equal(expected, result);
    });

    it('tests get color if index equal 1', function () {
        var index = 1;
        var data = [{'html': 'test'}, {'html': 1}, {'html': 1}];
        var expected = 'black';

        var result = controller.getCSS(data, index, false);

        assert.equal(expected, result);
    });

    it('tests get color if current data equal previous month data', function () {
        var index = 2;
        var data = [{'html': 'test'}, {'html': 1}, {'html': 1}];

        var expected = 'black';

        var result = controller.getCSS(data, index, false);

        assert.equal(expected, result);
    });

    it('tests get color if current data equal previous month data when round up to 2 digits', function () {
        var index = 2;
        var data = [{'html': 'test'}, {'html': 1.11443907}, {'html': 1.1123987007}];

        var expected = 'black';

        var result = controller.getCSS(data, index, false);

        assert.equal(expected, result);
    });

    it('tests get color if previous month data are less than current data', function () {
        var index = 2;
        var data = [{'html': 'test'}, {'html': 1.11}, {'html': 1.12}];

        var expected = 'green fa fa-arrow-up';

        var result = controller.getCSS(data, index, false);

        assert.equal(expected, result);
    });

    it('tests get color if previous month data are bigger than current data', function () {
        var index = 2;
        var data = [{'html': 'test'}, {'html': 1.12}, {'html': 1.11}];

        var expected = 'red fa fa-arrow-down';

        var result = controller.getCSS(data, index, false);

        assert.equal(expected, result);
    });

    it('tests get color if previous month data are less than current data and reverse is true', function () {
        var index = 2;
        var data = [{'html': 'test'}, {'html': 1.11}, {'html': 1.12}];

        var expected = 'red fa fa-arrow-up';

        var result = controller.getCSS(data, index, true);

        assert.equal(expected, result);
    });

    it('tests get color if previous month data are bigger than current data and reverse is true', function () {
        var index = 2;
        var data = [{'html': 'test'}, {'html': 1.12}, {'html': 1.11}];

        var expected = 'green fa fa-arrow-down';

        var result = controller.getCSS(data, index, true);

        assert.equal(expected, result);
    });

    it('tests go to report', function () {
        var expected = '/fact_sheets/test';

        controller.goToReport('test');
        var result = $location.path();

        assert.equal(expected, result);
    });

    it('tests go back', function () {
        controller.report = 'test';
        controller.title = 'test';
        $location.path('test');

        var expected = '/fact_sheets/';
        controller.goBack();
        var result = $location.path();

        assert.equal(expected, result);
        assert.equal(controller.report, null);
        assert.equal(controller.title, null);
    });
});