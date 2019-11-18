/* global module, inject, chai, LocationFilterController, LocationModalController */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Location Filter Controller', function () {

    pageData.registerUrl('icds_locations', 'icds_locations');

    var scope, controller, $uibModal, $location, storageService, locationsService;

    var mockLocationCache = {
        'root': [],
        '9951736acfe54c68948225cc05fbbd63': [{
            location_type_name: "state",
            parent_id: null,
            location_id: "9951736acfe54c68948225cc05fbbd63",
            name: "Chhattisgarh",
            user_have_access: 1,
            user_have_access_to_parent: 0,
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
        user_have_access: 1,
        user_have_access_to_parent: 0,
    }, [], [], [],
    ];

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
        $provide.constant("allUserLocationId", []);
        $provide.constant("haveAccessToAllLocations", true);
        $provide.constant("isAlertActive", false);
        $provide.constant("locationHierarchy", [
            ['state', [null]],
            ['district', ['state']],
            ['block', ['district']],
            ['supervisor', ['block']],
            ['awc', ['supervisor']],
        ]);
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
            [{"name": "state", "parents": [null], "level": 0}],
            [{"name": "district", "parents": ["state"], "level": 1}],
            [{"name": "block", "parents": ["district"], "level": 2}],
            [{"name": "supervisor", "parents": ["block"], "level": 3}],
            [{"name": "awc", "parents": ["supervisor"], "level": 4}],
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
            user_have_access: 1,
            user_have_access_to_parent: 0,
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
                "name": "Chhattisgarh",
                "user_have_access": 1,
                "user_have_access_to_parent": 0,
            },
            {
                "name": "All",
                "location_id": "all",
                "user_have_access": 0,
                "user_have_access_to_parent": 1,
            },
            null,
            null,
        ];

        controller.onSelect(item, 1);
        var result = controller.selectedLocations;

        assert.deepEqual(expected, result);
    });

    it('tests user have access to all locations', function() {
        var mockLocations = [
            {'location_id': 'loc_1', 'name': 'loc_1', 'user_have_access': true},
            {'location_id': 'loc_2', 'name': 'loc_2', 'user_have_access': true},
            {'location_id': 'loc_3', 'name': 'loc_3', 'user_have_access': true},
            {'location_id': 'loc_4', 'name': 'loc_4', 'user_have_access': true},
        ];
        assert.equal(true, controller.userHaveAccessToAllLocations(mockLocations));
    });

    it('tests user dont have access to all locations', function() {
        var mockLocations = [
            {'location_id': 'loc_1', 'name': 'loc_1', 'user_have_access': true},
            {'location_id': 'loc_2', 'name': 'loc_2', 'user_have_access': false},
            {'location_id': 'loc_3', 'name': 'loc_3', 'user_have_access': true},
            {'location_id': 'loc_4', 'name': 'loc_4', 'user_have_access': true},
        ];
        assert.equal(false, controller.userHaveAccessToAllLocations(mockLocations));
    });

    it('tests user location Id is null', function() {
        controller.userLocationId = "null";
        assert.equal(true, controller.userLocationIdIsNull());
        controller.userLocationId = "undefined";
        assert.equal(true, controller.userLocationIdIsNull());
        controller.userLocationId = '';
        assert.equal(false, controller.userLocationIdIsNull());
        controller.userLocationId = 'test_location_id';
        assert.equal(false, controller.userLocationIdIsNull());
    });

    it('tests user location id in locations', function() {
        var mockLocations = [
            {'location_id': 'loc_1', 'name': 'loc_1', 'user_have_access': true},
            {'location_id': 'loc_2', 'name': 'loc_2', 'user_have_access': true},
            {'location_id': 'loc_3', 'name': 'loc_3', 'user_have_access': true},
            {'location_id': 'loc_4', 'name': 'loc_4', 'user_have_access': true},
        ];
        controller.allUserLocationId = ['loc_2'];
        assert.equal(true, controller.isUserLocationIn(mockLocations));
    });

    it('tests user location id not in locations', function() {
        var mockLocations = [
            {'location_id': 'loc_1', 'name': 'loc_1', 'user_have_access': true},
            {'location_id': 'loc_2', 'name': 'loc_2', 'user_have_access': true},
            {'location_id': 'loc_3', 'name': 'loc_3', 'user_have_access': true},
            {'location_id': 'loc_4', 'name': 'loc_4', 'user_have_access': true},
        ];
        controller.allUserLocationId = ['loc_5'];
        assert.equal(false, controller.isUserLocationIn(mockLocations));
    });
});

describe('Location Modal Controller', function () {

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
        $provide.constant("isAlertActive", false);
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
            user_have_access: 1,
            user_have_access_to_parent: 0,
        }],
    };

    var mockSelectedLocations = [{
        name: "All",
        location_id: "all",
        user_have_access: 1,
        user_have_access_to_parent: 0,
    }, {
        location_type_name: "state",
        parent_id: null,
        location_id: "9951736acfe54c68948225cc05fbbd63",
        name: "Chhattisgarh",
        user_have_access: 1,
        user_have_access_to_parent: 0,
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
                showSectorMessage: true,
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
            user_have_access: 1,
            user_have_access_to_parent: 0,
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
            user_have_access: 1,
            user_have_access_to_parent: 0,
        };

        var expected = [
            {
                "name": "All",
                "location_id": "all",
                "user_have_access": 1,
                "user_have_access_to_parent": 0,
            },
            {
                "location_type_name": "state",
                "parent_id": null,
                "location_id": "9951736acfe54c68948225cc05fbbd63",
                "name": "Chhattisgarh",
                "user_have_access": 1,
                "user_have_access_to_parent": 0,
            },
            null,
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
        expected = {
            "location_id": "9951736acfe54c68948225cc05fbbd63",
            "location_type_name": "state",
            "name": "Chhattisgarh",
            "parent_id": null,
            "user_have_access": 1,
            "user_have_access_to_parent": 0,
        };
        result = controller.selectedLocationId;

        assert.deepEqual(expected, result);
        chai.expect(modalInstance.close).to.have.been.called;
    });

    it('tests reset when user id not exist', function () {
        controller.userLocationId = null;
        var expected = [
            {
                "name": "All",
                "location_id": "all",
                "user_have_access": 0,
                "user_have_access_to_parent": 1,
            },
        ];

        controller.reset();
        var result = controller.selectedLocations;

        assert.deepEqual(expected, result);
        assert.equal(null, controller.selectedLocationId);
    });

    it('tests reset when user id exist', function () {
        controller.userLocationId = '9951736acfe54c68948225cc05fbbd63';
        var expected = [
            {
                "name": "All",
                "location_id": "all",
                "user_have_access": 1,
                "user_have_access_to_parent": 0,
            },
            {
                "location_type_name": "state",
                "parent_id": null,
                "location_id": "9951736acfe54c68948225cc05fbbd63",
                "name": "Chhattisgarh",
                "user_have_access": 1,
                "user_have_access_to_parent": 0,
            },
            {   "name": "All",
                "location_id": "all",
                "user_have_access": 0,
                "user_have_access_to_parent": 1,
            },
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

describe('Location Modal Controller restrictions', function () {

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
        $provide.constant("isAlertActive", false);
    }));

    var scope, modalInstance, controller, $location;

    var mockHierarchy = [['awc', ['supervisor']], {'selected': null},
        ['block', ['district']], {'selected': null},
        ['district', ['state']], {'selected': null},
        ['state', [null]], {'selected': null},
        ['supervisor', ['block']], {'selected': null},
    ];

    beforeEach(function () {
        inject(function ($rootScope, $controller, _$uibModal_, _$location_, locationsService) {
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
                selectedLocationId: '',
                hierarchy: mockHierarchy,
                selectedLocations: [],
                locationsCache: [],
                maxLevel: 5,
                userLocationId: null,
                showMessage: true,
                showSectorMessage: true,
            });
        });
    });

    it('tests disabled dropdowns if user assign to awc', function () {
        var mockLocationCache = {
            'root': [{
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_state': [{
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_district': [{
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_block': [{
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_sector': [{
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc",
                name: "Test AWC",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }],
        };

        var mockSelectedLocations = [
            {
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc",
                name: "Test AWC",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            },
        ];
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        controller.userLocationId = 'test_awc';
        controller.selectedLocationId = 'test_awc';
        assert.equal(true, controller.disabled(0));
        assert.equal(true, controller.disabled(1));
        assert.equal(true, controller.disabled(2));
        assert.equal(true, controller.disabled(3));
        assert.equal(true, controller.disabled(4));
    });

    it('tests disabled dropdowns if user assign to sector', function () {
        var mockLocationCache = {
            'root': [{
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_state': [{
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_district': [{
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_block': [{
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }],
            'test_sector': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc_1",
                name: "Test AWC 1",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
        };

        var mockSelectedLocations = [
            {
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc",
                name: "Test AWC",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            },
        ];
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        controller.userLocationId = 'test_sector';
        controller.selectedLocationId = 'test_sector';
        assert.equal(true, controller.disabled(0));
        assert.equal(true, controller.disabled(1));
        assert.equal(true, controller.disabled(2));
        assert.equal(true, controller.disabled(3));
        assert.equal(false, controller.disabled(4));
    });

    it('tests disabled dropdowns if user assign to block', function () {
        var mockLocationCache = {
            'root': [{
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_state': [{
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_district': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_block': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
            'test_sector': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc_1",
                name: "Test AWC 1",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
        };

        var mockSelectedLocations = [
            {
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc",
                name: "Test AWC",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            },
        ];
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        controller.userLocationId = 'test_block';
        controller.selectedLocationId = 'test_block';
        assert.equal(true, controller.disabled(0));
        assert.equal(true, controller.disabled(1));
        assert.equal(false, controller.disabled(2));
        assert.equal(false, controller.disabled(3));
        assert.equal(false, controller.disabled(4));
    });

    it('tests disabled dropdowns if user assign to district', function () {
        var mockLocationCache = {
            'root': [{
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }],
            'test_state': [{
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }],
            'test_district': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
            'test_block': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
            'test_sector': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc_1",
                name: "Test AWC 1",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
        };

        var mockSelectedLocations = [
            {
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 0,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc",
                name: "Test AWC",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            },
        ];
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        controller.userLocationId = 'test_district';
        controller.selectedLocationId = 'test_district';
        assert.equal(true, controller.disabled(0));
        assert.equal(true, controller.disabled(1));
        assert.equal(false, controller.disabled(2));
        assert.equal(false, controller.disabled(3));
        assert.equal(false, controller.disabled(4));
    });

    it('tests disabled dropdowns if user assign to state', function () {
        var mockLocationCache = {
            'root': [{
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }],
            'test_state': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
            'test_district': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
            'test_block': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
            'test_sector': [{
                name: 'All',
                location_id: 'all',
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc_1",
                name: "Test AWC 1",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }],
        };

        var mockSelectedLocations = [
            {
                location_type_name: "state",
                parent_id: null,
                location_id: "test_state",
                name: "Test State",
                user_have_access: 1,
                user_have_access_to_parent: 1,
            }, {
                location_type_name: "district",
                parent_id: "test_state",
                location_id: "test_district",
                name: "Test District",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "block",
                parent_id: "test_district",
                location_id: "test_block",
                name: "Test Block",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "sector",
                parent_id: "test_block",
                location_id: "test_sector",
                name: "Test Sector",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            }, {
                location_type_name: "awc",
                parent_id: "test_sector",
                location_id: "test_awc",
                name: "Test AWC",
                user_have_access: 1,
                user_have_access_to_parent: 0,
            },
        ];
        controller.selectedLocations = mockSelectedLocations;
        controller.locationsCache = mockLocationCache;
        controller.userLocationId = 'test_state';
        controller.selectedLocationId = 'test_state';
        assert.equal(true, controller.disabled(0));
        assert.equal(false, controller.disabled(1));
        assert.equal(false, controller.disabled(2));
        assert.equal(false, controller.disabled(3));
        assert.equal(false, controller.disabled(4));
    });
});
