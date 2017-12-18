/* global module, inject, chai, LocationFilterController, LocationModalController */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Location Filter Controller', function () {

    beforeEach(module('icdsApp'));

    var scope, controller, $uibModal, $location, storageService, locationsService;

    var mockLocationCache = {
        'root': [],
        '9951736acfe54c68948225cc05fbbd63': [{
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        }],
    };

    var mockSelectedLocations = [{
        name: "All",
        location_id: "all",
    }, {
        location_type_name: "state",
        parent_id: null,
        location_id: "9951736acfe54c68948225cc05fbbd63",
        name: "Chhattisgarh",
    }, [], [], [],
    ];

    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
        $provide.constant("locationHierarchy", [['awc', ['supervisor']], ['block', ['district']],
            ['district', ['state']], ['state', [null]], ['supervisor', ['block']]]);
    }));

    beforeEach(function () {
        inject(function ($rootScope, $controller, _$uibModal_, _$location_, _storageService_, _locationsService_) {
            $uibModal = _$uibModal_;
            $location = _$location_;
            scope = $rootScope.$new();
            storageService = _storageService_;
            locationsService = _locationsService_;

            controller = $controller(LocationFilterController, {
                $scope: scope,
                $uibModal: $uibModal,
                $location: $location,
                storageService: storageService,
                locationsService: locationsService,
            });
        });
    });

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests call open modal', function () {
        var open = sinon.spy($uibModal, 'open');
        controller.open();
        chai.expect(open).to.have.been.called;
    });

    it('tests init hierarchy', function () {
        var result = controller.hierarchy;
        var expected = [
            [{"name": "awc", "parents": ["supervisor"], "level": 4}],
            [{"name": "block", "parents": ["district"], "level": 2}],
            [{"name": "district", "parents": ["state"], "level": 1}],
            [{"name": "state", "parents": [null], "level": 0}],
            [{"name": "supervisor", "parents": ["block"], "level": 3}],
        ];

        assert.deepEqual(expected, result);
        assert.equal(controller.maxLevel, 4);
    });

    it('tests get placeholder', function () {
        var mockLocationType = [{"name": "state", "parents": ["state"], "level": 1}];

        var expected = 'Location';
        var result = controller.getPlaceholder(mockLocationType);
        assert.equal(expected, result);
    });

    it('tests get locations for level 1', function () {
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        var level = 1;
        var expected = [];

        var result = controller.getLocationsForLevel(level);
        assert.deepEqual(expected, result);
    });

    it('tests get locations for level 2', function () {
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        var level = 2;
        var expected = [{
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        }];

        var result = controller.getLocationsForLevel(level);
        assert.deepEqual(expected, result);
    });

    it('tests on select', function () {
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        var item = {
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        };

        var expected = [
            {"name": "All", "location_id": "all"},
            {
                "location_type_name": "state",
                "parent_id": null,
                "location_id": "9951736acfe54c68948225cc05fbbd63",
                "name": "Chhattisgarh"
            },
            {"name": "All", "location_id": "all"},
            null,
            null,
        ];

        controller.onSelect(item, 1);
        var result = controller.selectedLocations;

        assert.deepEqual(expected, result);
    });
});

describe('Location Modal Controller', function () {

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
    }));

    var scope, modalInstance, controller, $uibModal, $location;

    var mockHierarchy = [['awc', ['supervisor']], {'selected': null},
        ['block', ['district']], {'selected': null},
        ['district', ['state']], {'selected': null},
        ['state', [null]], {'selected': null},
        ['supervisor', ['block']], {'selected': null},
    ];

    var mockLocationCache = {
        'root': [],
        '9951736acfe54c68948225cc05fbbd63': [{
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        }],
    };

    var mockSelectedLocations = [{
        name: "All",
        location_id: "all",
    }, {
        location_type_name: "state",
        parent_id: null,
        location_id: "9951736acfe54c68948225cc05fbbd63",
        name: "Chhattisgarh",
    }, [], [], [],
    ];

    var mockSelectedLocationId = "9951736acfe54c68948225cc05fbbd63";

    beforeEach(function () {
        inject(function ($rootScope, $controller, _$uibModal_, _$location_, locationsService) {
            $uibModal = _$uibModal_;
            $location = _$location_;
            scope = $rootScope.$new();

            modalInstance = {
                close: sinon.spy(),
                dismiss: sinon.spy(),
                result: {
                    then: sinon.spy(),
                },
            };

            controller = $controller(LocationModalController, {
                $scope: scope,
                $uibModalInstance: modalInstance,
                $location: $location,
                locationsService: locationsService,
                selectedLocationId: mockSelectedLocationId,
                hierarchy: mockHierarchy,
                selectedLocations: mockSelectedLocations,
                locationsCache: mockLocationCache,
                maxLevel: 5,
                userLocationId: null,
                showMessage: true,
            });
        });
    });

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests call open modal', function () {
        chai.expect($uibModal.open).to.have.been.called;
    });

    it('tests call close modal', function () {
        controller.apply();
        chai.expect(modalInstance.close).to.have.been.called;
    });

    it('tests call dismiss modal', function () {
        controller.close();
        chai.expect(modalInstance.dismiss).to.have.been.called;
    });

    it('tests get placeholder', function () {
        var mockLocationType = [{"name": "state", "parents": ["state"], "level": 1}];

        var expected = 'State';
        var result = controller.getPlaceholder(mockLocationType);
        assert.equal(expected, result);
    });

    it('tests get locations for level 1', function () {
        var level = 1;
        var expected = [];

        var result = controller.getLocationsForLevel(level);
        assert.deepEqual(expected, result);
    });

    it('tests get locations for level 2', function () {
        var level = 2;
        var expected = [{
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        }];

        var result = controller.getLocationsForLevel(level);
        assert.deepEqual(expected, result);
    });

    it('tests disabled when user id not exist', function () {
        var level = 1;
        var expected = false;
        var result = controller.disabled(level);
        assert.equal(expected, result);
    });

    it('tests disabled when user id exist', function () {
        var level = 1;
        var expected = false;
        var result = controller.disabled(level);
        assert.equal(expected, result);
    });

    it('tests on select', function () {
        var item = {
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
        };

        var expected = [
            {"name": "All", "location_id": "all"},
            {
                "location_type_name": "state",
                "parent_id": null,
                "location_id": "9951736acfe54c68948225cc05fbbd63",
                "name": "Chhattisgarh",
            },
            {"name": "All", "location_id": "all"},
            null,
            null,
            null,
        ];

        controller.onSelect(item, 1);
        var result = controller.selectedLocations;

        assert.deepEqual(expected, result);
        assert.equal(true, controller.showMessage);
    });

    it('tests apply', function () {
        var expected = '9951736acfe54c68948225cc05fbbd63';
        var result = controller.selectedLocationId;
        assert.equal(expected, result);

        controller.apply();
        expected = {"name": "All", "location_id": "all"};
        result = controller.selectedLocationId;

        assert.deepEqual(expected, result);
        chai.expect(modalInstance.close).to.have.been.called;
    });

    it('tests reset when user id not exist', function () {
        controller.userLocationId = null;
        var expected = [{"name": "All", "location_id": "all"}];

        controller.reset();
        var result = controller.selectedLocations;

        assert.deepEqual(expected, result);
        assert.equal(null, controller.selectedLocationId);
    });

    it('tests reset when user id exist', function () {
        controller.userLocationId = '9951736acfe54c68948225cc05fbbd63';
        var expected = [
            {"name": "All", "location_id": "all"},
            {
                "location_type_name": "state",
                "parent_id": null,
                "location_id": "9951736acfe54c68948225cc05fbbd63",
                "name": "Chhattisgarh",
            },
            {"name": "All", "location_id": "all"},
        ];

        controller.reset();
        var result = controller.selectedLocations;

        assert.deepEqual(expected, result);
        assert.equal("9951736acfe54c68948225cc05fbbd63", controller.selectedLocationId);
    });

    it('tests is visible', function () {
        var level = 0;
        var expected = true;

        var result = controller.isVisible(level);

        assert.equal(expected, result);
    });

    it('tests is not visible', function () {
        var level = 1;
        var expected = false;

        var result = controller.isVisible(level);

        assert.equal(expected, result);
    });
});