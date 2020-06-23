/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Download Directive', function () {

    var numberOfReports = 12;
    describe('Download Directive main functionalities', function() {
        var $scope, $httpBackend, controller;

        pageData.registerUrl('icds-ng-template', 'template');
        pageData.registerUrl('icds_locations', 'icds_locations');
        beforeEach(module('icdsApp', function ($provide) {
            $provide.constant("userLocationId", null);
            $provide.constant("locationHierarchy", [
                ['state', [null]],
                ['district', ['state']],
                ['block', ['district']],
                ['supervisor', ['block']],
                ['awc', ['supervisor']],
            ]);
            $provide.constant("haveAccessToFeatures", false);
            $provide.constant("userLocationType", 'state');
            $provide.constant("haveAccessToAllLocations", false);
            $provide.constant("allUserLocationId", []);
            $provide.constant("isAlertActive", false);
        }));

        beforeEach(inject(function ($rootScope, $compile, _$httpBackend_) {
            $scope = $rootScope.$new();
            $httpBackend = _$httpBackend_;

            var mockLocation = {
                "locations": [{
                    "location_type_name": "state", "parent_id": null,
                    "location_id": "9951736acfe54c68948225cc05fbbd63", "name": "Chhattisgarh",
                }],
            };

            $httpBackend.expectGET('template').respond(200, '<div></div>');
            $httpBackend.expectGET('icds_locations').respond(200, mockLocation);

            var fakeDate = new Date(2016, 9, 1);
            var clock = sinon.useFakeTimers(fakeDate.getTime());

            var element = window.angular.element("<download data='test'></download>");
            var compiled = $compile(element)($scope);

            $httpBackend.flush();
            $scope.$digest();
            controller = compiled.controller('download');
            clock.restore();
        }));

        it('tests instantiate the controller properly', function () {
            chai.expect(controller).not.to.be.a('undefined');
        });

        it('tests initialize months', function () {
            controller.selectedYear = 2015;
            controller.onSelectYear({id: 2015, value: 2015});
            var expected = [
                {"name": "January", "id": 1},
                {"name": "February", "id": 2},
                {"name": "March", "id": 3},
                {"name": "April", "id": 4},
                {"name": "May", "id": 5},
                {"name": "June", "id": 6},
                {"name": "July", "id": 7},
                {"name": "August", "id": 8},
                {"name": "September", "id": 9},
                {"name": "October", "id": 10},
                {"name": "November", "id": 11},
                {"name": "December", "id": 12},
            ];

            assert.deepEqual(expected, controller.months);
        });

        it('tests initialize months when we have current year', function () {
            var expected = [
                {"name": "January", "id": 1},
                {"name": "February", "id": 2},
                {"name": "March", "id": 3},
                {"name": "April", "id": 4},
                {"name": "May", "id": 5},
                {"name": "June", "id": 6},
                {"name": "July", "id": 7},
                {"name": "August", "id": 8},
                {"name": "September", "id": 9},
            ];

            assert.deepEqual(expected, controller.months);
        });

        it('tests selected month', function () {
            var result = controller.selectedMonth;
            var expected = 9;
            assert.equal(expected, result);
        });

        it('tests initialize years', function () {
            var result = controller.years;
            var expected = [];
            assert.deepEqual(expected, result);
        });

        it('tests selected year', function () {
            var result = controller.selectedYear;
            var expected = 2016;
            assert.equal(expected, result);
        });

        it('tests initialize hierarchy', function () {
            var result = controller.hierarchy;
            var expected = [
                [{"name": "state", "parents": [null], "level": 0}],
                [{"name": "district", "parents": ["state"], "level": 1}],
                [{"name": "block", "parents": ["district"], "level": 2}],
                [{"name": "supervisor", "parents": ["block"], "level": 3}],
                [{"name": "awc", "parents": ["supervisor"], "level": 4}],
            ];

            assert.deepEqual(expected, result);
        });

        it('tests get placeholder when district', function () {
            var mockLocationType = [{"name": "district", "parents": ["state"], "level": 1}];
            var result = controller.getPlaceholder(mockLocationType);

            var expected = 'district';
            assert.equal(expected, result);
        });

        it('tests get placeholder when state', function () {
            var mockLocationType = [{"name": "state", "parents": ["state"], "level": 1}];
            var result = controller.getPlaceholder(mockLocationType);

            var expected = 'National';
            assert.equal(expected, result);
        });

        it('tests get placeholder when state and child beneficiary list is selected', function () {
            controller.selectedIndicator = 6;
            var mockLocationType = [{"name": "state", "parents": ["state"], "level": 1}];

            var expected = 'Select State';
            var result = controller.getPlaceholder(mockLocationType);
            assert.equal(expected, result);
        });

        it('tests get placeholder when state and child growth tracker list is selected', function () {
            controller.selectedIndicator = 13;
            var mockLocationType = [{"name": "state", "parents": ["state"], "level": 1}];

            var expected = 'Select State';
            var result = controller.getPlaceholder(mockLocationType);
            assert.equal(expected, result);
        });

        it('tests get placeholder when state and aww activity report is selected', function () {
            controller.selectedIndicator = 14;
            var mockLocationType = [{"name": "state", "parents": ["state"], "level": 1}];

            var expected = 'National';
            var result = controller.getPlaceholder(mockLocationType);
            assert.equal(expected, result);
        });


        it('tests get locations for level', function () {
            var level = 0;
            var expected = [
                {name: "National", location_id: "all"},
                {
                    location_type_name: "state",
                    parent_id: null,
                    location_id: "9951736acfe54c68948225cc05fbbd63",
                    name: "Chhattisgarh",
                }];

            var result = controller.getLocationsForLevel(level);
            assert.deepEqual(expected, result);
        });

        it('tests get formats when child beneficiary list is selected', function () {
            controller.selectedIndicator = 6;
            var expected = [{"id": "csv", "name": "CSV"}];

            var result = controller.getFormats();
            assert.deepEqual(expected, result);
        });

        it('tests get formats when child growth tracker list is selected', function () {
            controller.selectedIndicator = 13;
            var expected = [{"id": "csv", "name": "CSV"}, {"id": "xlsx", "name": "Excel"}];

            var result = controller.getFormats();
            assert.deepEqual(expected, result);
        });

        it('tests get formats when child beneficiary list is not selected', function () {
            controller.selectedIndicator = 5;
            var expected = [{"id": "csv", "name": "CSV"}, {"id": "xlsx", "name": "Excel"}];

            var result = controller.getFormats();
            assert.deepEqual(expected, result);
        });

        it('tests on indicator select when child growth tracker list is selected', function () {
            controller.selectedIndicator = 13;
            var result = controller.isChildGrowthTrackerSelected();
            assert.isTrue(result);
        });

        it('tests on indicator select when child growth tracker list is not selected', function () {
            controller.selectedIndicator = 12;
            var result = controller.isChildGrowthTrackerSelected();
            assert.isFalse(result);
        });

        it('tests on indicator select when aww activity report is not selected', function () {
            controller.selectedIndicator = 9;
            var result = controller.isAwwActivityReportSelected();
            assert.isFalse(result);
        });


        it('tests on indicator select when child beneficiary list is selected', function () {
            controller.selectedIndicator = 6;
            var expected = "csv";

            controller.onIndicatorSelect();
            var result = controller.selectedFormat;

            assert.equal(expected, result);
        });

        it('tests on indicator select when aww activity report is selected', function () {
            controller.selectedIndicator = 14;
            var result = controller.isAwwActivityReportSelected();
            assert.isTrue(result);

        });

        it('tests isDistrictOrBelowSelected - state selected', function () {
            controller.selectedLocations = ['state', 'all'];
            var result = controller.isDistrictOrBelowSelected();
            assert.isFalse(result);
        });

        it('tests isDistrictOrBelowSelected - district selected', function () {
            controller.selectedLocations = ['state', 'district'];
            var result = controller.isDistrictOrBelowSelected();
            assert.isTrue(result);
        });

        it('tests isBlockOrBelowSelected - district selected', function () {
            controller.selectedLocations = ['state', 'district', 'all'];
            var result = controller.isBlockOrBelowSelected();
            assert.isFalse(result);
        });

        it('tests isBlockOrBelowSelected - block selected', function () {
            controller.selectedLocations = ['state', 'district', 'block'];
            var result = controller.isBlockOrBelowSelected();
            assert.isTrue(result);
        });

        it('tests isAWCsSelected - AWC not selected', function () {
            controller.selectedAWCs = [];
            var result = controller.isAWCsSelected();
            assert.isFalse(result);
        });

        it('tests isAWCsSelected - AWC selected', function () {
            controller.selectedAWCs = ['awc_1', 'awc_2'];
            var result = controller.isAWCsSelected();
            assert.isTrue(result);
        });

        it('tests isCombinedPDFSelected', function () {
            controller.selectedIndicator = 7;
            controller.selectedPDFFormat = 'one';
            var result = controller.isCombinedPDFSelected();
            assert.isTrue(result);
        });

        it('tests isTakeHomeRatioReportSelected - THR selected', function () {
            controller.selectedIndicator = 10;
            var result = controller.isTakeHomeRationReportSelected();
            assert.isTrue(result);
        });

        it('tests isTakeHomeRatioReportSelected - THR not selected', function () {
            controller.selectedIndicator = 9;
            var result = controller.isTakeHomeRationReportSelected();
            assert.isFalse(result);
        });

        it('tests isPPRselecected - PPR selected', function () {
            controller.selectedIndicator = 15;
            var result = controller.isPPRSelected();
            assert.isTrue(result);
        });

        it('tests isPPRselecected - PPR not selected', function () {
            controller.selectedIndicator = 9;
            var result = controller.isPPRSelected();
            assert.isFalse(result);
        });

        it('test to check if current month is enabled after first three days', function () {
            var fakeDate = new Date(2019, 8, 4);
            var clock = sinon.useFakeTimers(fakeDate.getTime());
            controller.selectedIndicator = 1;
            controller.selectedYear = fakeDate.getFullYear();
            controller.onSelectYear({id: fakeDate.getFullYear(), value: fakeDate.getFullYear()});
            var expected = [
                {"name": "January", "id": 1},
                {"name": "February", "id": 2},
                {"name": "March", "id": 3},
                {"name": "April", "id": 4},
                {"name": "May", "id": 5},
                {"name": "June", "id": 6},
                {"name": "July", "id": 7},
                {"name": "August", "id": 8},
                {"name": "September", "id": 9},
            ];
            assert.deepEqual(expected, controller.months);
            clock.restore();
        });

        it('test to check if current month is not enabled before first three days', function () {
            var fakeDate = new Date(2019, 8, 2);
            var clock = sinon.useFakeTimers(fakeDate.getTime());
            controller.selectedIndicator = 1;
            controller.selectedYear = fakeDate.getFullYear();
            controller.onSelectYear({id: fakeDate.getFullYear(), value: fakeDate.getFullYear()});
            var expected = [
                {"name": "January", "id": 1},
                {"name": "February", "id": 2},
                {"name": "March", "id": 3},
                {"name": "April", "id": 4},
                {"name": "May", "id": 5},
                {"name": "June", "id": 6},
                {"name": "July", "id": 7},
                {"name": "August", "id": 8},
            ];
            assert.deepEqual(expected, controller.months);
            clock.restore();
        });

        it('test to check if AWW performance report is downloadable only till last month ' +
            'after current month 15th ', function () {
            var fakeDate = new Date(2019, 8, 17);
            var clock = sinon.useFakeTimers(fakeDate.getTime());
            controller.selectedIndicator = 8;
            controller.selectedYear = fakeDate.getFullYear();
            controller.onSelectYear({id: fakeDate.getFullYear(), value: fakeDate.getFullYear()});
            var expected = [
                {"name": "January", "id": 1},
                {"name": "February", "id": 2},
                {"name": "March", "id": 3},
                {"name": "April", "id": 4},
                {"name": "May", "id": 5},
                {"name": "June", "id": 6},
                {"name": "July", "id": 7},
                {"name": "August", "id": 8},
            ];
            assert.deepEqual(expected, controller.months);
            clock.restore();
        });

        it('test to check if AWW performance report is downloadable only till last before month ' +
            'before current month 15th ', function () {
            var fakeDate = new Date(2019, 8, 5);
            var clock = sinon.useFakeTimers(fakeDate.getTime());
            controller.selectedIndicator = 8;
            controller.selectedYear = fakeDate.getFullYear();
            controller.onSelectYear({id: fakeDate.getFullYear(), value: fakeDate.getFullYear()});
            var expected = [
                {"name": "January", "id": 1},
                {"name": "February", "id": 2},
                {"name": "March", "id": 3},
                {"name": "April", "id": 4},
                {"name": "May", "id": 5},
                {"name": "June", "id": 6},
                {"name": "July", "id": 7},
            ];
            assert.deepEqual(expected, controller.months);
            clock.restore();
        });

    });

    describe('Download Directive have access to features', function() {
        var $scope, $httpBackend, controller;

        pageData.registerUrl('icds-ng-template', 'template');
        pageData.registerUrl('icds_locations', 'icds_locations');
        beforeEach(module('icdsApp', function ($provide) {
            $provide.constant("userLocationId", null);
            $provide.constant("locationHierarchy", [
                ['awc', ['supervisor']],
                ['block', ['district']],
                ['district', ['state']],
                ['state', [null]],
                ['supervisor', ['block']]]);
            $provide.constant("haveAccessToFeatures", true);
            $provide.constant("userLocationType", 'state');
            $provide.constant("isAlertActive", false);
            $provide.constant("haveAccessToAllLocations", false);
            $provide.constant("allUserLocationId", []);
        }));

        beforeEach(inject(function ($rootScope, $compile, _$httpBackend_) {
            $scope = $rootScope.$new();
            $httpBackend = _$httpBackend_;

            var mockLocation = {
                "locations": [{
                    "location_type_name": "state", "parent_id": null,
                    "location_id": "9951736acfe54c68948225cc05fbbd63", "name": "Chhattisgarh",
                }],
            };

            $httpBackend.expectGET('template').respond(200, '<div></div>');
            $httpBackend.expectGET('icds_locations').respond(200, mockLocation);

            var fakeDate = new Date(2016, 9, 1);
            var clock = sinon.useFakeTimers(fakeDate.getTime());

            var element = window.angular.element("<download data='test'></download>");
            var compiled = $compile(element)($scope);

            $httpBackend.flush();
            $scope.$digest();
            controller = compiled.controller('download');
            clock.restore();
        }));

        it('tests that all users have access to ISSNIP monthly register', function () {

            var length = controller.indicators.length;
            assert.equal(numberOfReports + 3, length);
        });

        it('tests first possible data choice on THR raport', function () {
            var fakeDate = new Date(2020, 8, 1);
            var clock = sinon.useFakeTimers(fakeDate);
            var expectedMonth = 7;
            var expectedFirstYear = 2019;

            controller.selectedYear = 2019;
            controller.selectedIndicator = 10;
            controller.onIndicatorSelect();

            var firstAvailableMonth = controller.months[0].id;
            var actualFirstYear = controller.selectedYear;

            assert.equal(expectedMonth, firstAvailableMonth);
            assert.equal(expectedFirstYear, actualFirstYear);
            clock.restore();
        });

        it('tests latest possible data choice on THR raport', function () {
            var fakeDate = new Date(2023, 8, 15);
            var clock = sinon.useFakeTimers(fakeDate);
            var expectedMonth = 8;
            var expectedYear = 2023;
            controller.yearsCopy = _.range(2017, 2024);

            controller.selectedIndicator = 10;
            controller.onIndicatorSelect();

            var m = controller.months;
            var y = controller.yearsCopy;
            var actualMonth = m[m.length - 1].id - 1;
            var actualYear = y[y.length - 1];

            assert.equal(expectedMonth, actualMonth);
            assert.equal(expectedYear, actualYear);
            clock.restore();
        });

        it('tests THR Report AWC hierarchy reduction', function () {
            for (var i = 0; i < 5; i++) {
                controller.hierarchy[i].selected = i;
                controller.selectedLocations[i] = i;
            }
            controller.selectedIndicator = 10;
            controller.onIndicatorSelect();

            var awcHierarchy = controller.hierarchy[4].selected;
            var awcLocation = controller.selectedLocations[4];

            assert.isNull(awcHierarchy);
            assert.isNull(awcLocation);
        });
    });

    describe('Download Directive dont have access to features', function() {
        var $scope, $httpBackend, controller;

        pageData.registerUrl('icds-ng-template', 'template');
        pageData.registerUrl('icds_locations', 'icds_locations');
        beforeEach(module('icdsApp', function ($provide) {
            $provide.constant("userLocationId", null);
            $provide.constant("locationHierarchy", [
                ['awc', ['supervisor']],
                ['block', ['district']],
                ['district', ['state']],
                ['state', [null]],
                ['supervisor', ['block']]]);
            $provide.constant("haveAccessToFeatures", false);
            $provide.constant("userLocationType", 'state');
            $provide.constant("isAlertActive", false);
            $provide.constant("haveAccessToAllLocations", false);
            $provide.constant("allUserLocationId", []);
        }));

        beforeEach(inject(function ($rootScope, $compile, _$httpBackend_) {
            $scope = $rootScope.$new();
            $httpBackend = _$httpBackend_;

            var mockLocation = {
                "locations": [{
                    "location_type_name": "state", "parent_id": null,
                    "location_id": "9951736acfe54c68948225cc05fbbd63", "name": "Chhattisgarh",
                }],
            };

            $httpBackend.expectGET('template').respond(200, '<div></div>');
            $httpBackend.expectGET('icds_locations').respond(200, mockLocation);

            var fakeDate = new Date(2016, 9, 1);
            var clock = sinon.useFakeTimers(fakeDate.getTime());

            var element = window.angular.element("<download data='test'></download>");
            var compiled = $compile(element)($scope);

            $httpBackend.flush();
            $scope.$digest();
            controller = compiled.controller('download');
            clock.restore();
        }));

        it('tests that all users have access to ISSNIP monthly register', function () {
            var length = controller.indicators.length;
            assert.equal(numberOfReports - 1, length);
        });
    });

    describe('Download Directive have access to features', function () {
        var $scope, $httpBackend, controller;

        pageData.registerUrl('icds-ng-template', 'template');
        pageData.registerUrl('icds_locations', 'icds_locations');
        beforeEach(module('icdsApp', function ($provide) {
            $provide.constant("userLocationId", null);
            $provide.constant("locationHierarchy", [
                ['awc', ['supervisor']],
                ['block', ['district']],
                ['district', ['state']],
                ['state', [null]],
                ['supervisor', ['block']]]);
            $provide.constant("haveAccessToFeatures", true);
            $provide.constant("userLocationType", 'state');
            $provide.constant("isAlertActive", false);
            $provide.constant("haveAccessToAllLocations", false);
            $provide.constant("allUserLocationId", []);
        }));

        beforeEach(inject(function ($rootScope, $compile, _$httpBackend_) {
            $scope = $rootScope.$new();
            $httpBackend = _$httpBackend_;

            var mockLocation = {
                "locations": [{
                    "location_type_name": "state", "parent_id": null,
                    "location_id": "9951736acfe54c68948225cc05fbbd63", "name": "Chhattisgarh",
                }],
            };

            $httpBackend.expectGET('template').respond(200, '<div></div>');
            $httpBackend.expectGET('icds_locations').respond(200, mockLocation);

            var fakeDate = new Date(2016, 9, 1);
            var clock = sinon.useFakeTimers(fakeDate.getTime());

            var element = window.angular.element("<download data='test'></download>");
            var compiled = $compile(element)($scope);

            $httpBackend.flush();
            $scope.$digest();
            controller = compiled.controller('download');
            clock.restore();
        }));

        it('tests that all users have access to ISSNIP monthly register', function () {
            var length = controller.indicators.length;
            assert.equal(numberOfReports + 3, length);
        });
    });

    describe('Download Directive have access to features', function () {
        var $scope, $httpBackend, controller;

        pageData.registerUrl('icds-ng-template', 'template');
        pageData.registerUrl('icds_locations', 'icds_locations');
        beforeEach(module('icdsApp', function ($provide) {
            $provide.constant("userLocationId", null);
            $provide.constant("locationHierarchy", [
                ['awc', ['supervisor']],
                ['block', ['district']],
                ['district', ['state']],
                ['state', [null]],
                ['supervisor', ['block']]]);
            $provide.constant("haveAccessToFeatures", true);
            $provide.constant("userLocationType", 'block');
            $provide.constant("isAlertActive", false);
            $provide.constant("haveAccessToAllLocations", false);
            $provide.constant("allUserLocationId", []);
        }));

        beforeEach(inject(function ($rootScope, $compile, _$httpBackend_) {
            $scope = $rootScope.$new();
            $httpBackend = _$httpBackend_;

            var mockLocation = {
                "locations": [{
                    "location_type_name": "state", "parent_id": null,
                    "location_id": "9951736acfe54c68948225cc05fbbd63", "name": "Chhattisgarh",
                }],
            };

            $httpBackend.expectGET('template').respond(200, '<div></div>');
            $httpBackend.expectGET('icds_locations').respond(200, mockLocation);

            var fakeDate = new Date(2016, 9, 1);
            var clock = sinon.useFakeTimers(fakeDate.getTime());

            var element = window.angular.element("<download data='test'></download>");
            var compiled = $compile(element)($scope);

            $httpBackend.flush();
            $scope.$digest();
            controller = compiled.controller('download');
            clock.restore();
        }));

        it('tests that block user does not have access to dashboard usage report', function () {
            var length = controller.indicators.length;
            assert.equal(numberOfReports + 2, length);
        });
    });

});
