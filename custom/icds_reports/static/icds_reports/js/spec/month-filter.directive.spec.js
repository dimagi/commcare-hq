/* global module, inject, _, moment, chai, MonthFilterController, MonthModalController */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Month Filter Controller', function () {

    beforeEach(module('icdsApp'));

    var scope, controller, $uibModal, $location, storageService;

    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("userLocationId", null);
    }));

    beforeEach(function () {
        inject(function ($rootScope, $controller, _$uibModal_, _$location_, _storageService_) {
            $uibModal = _$uibModal_;
            $location = _$location_;
            scope = $rootScope.$new();
            storageService = _storageService_;

            controller = $controller(MonthFilterController, {
                $scope: scope,
                $uibModal: $uibModal,
                $location: $location,
                storageService: storageService,
            });
        });
    });

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests call open modal', function () {
        var open = sinon.spy($uibModal, 'open');
        controller.open();

        assert(open.calledOnce);
    });

    it('tests auto date change on invalid date in SDD', function () {
        var invalidDate = moment('2015-10-19').toDate();

        var clock = sinon.useFakeTimers(invalidDate.getTime());
        var open = sinon.spy(controller, 'open');

        $location.path('service_delivery_dashboard');

        controller.init();
        assert(controller.open.calledOnce);

        open.restore();
        clock.restore();
    });

    it('tests get placeholder', function () {
        var today = moment('2015-10-19').toDate();
        var clock = sinon.useFakeTimers(today.getTime());

        var result = controller.getPlaceholder();
        var expected = 'October 2015';

        assert.equal(expected, result);

        clock.restore();
    });
});

describe('Month Modal Controller', function () {

    beforeEach(module('icdsApp'));

    var modalInstance, controller, $location;

    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(function () {
        inject(function ($controller, _$location_) {
            $location = _$location_;

            var fakeDate = new Date(2017, 9, 1);
            var clock = sinon.useFakeTimers(fakeDate.getTime());

            modalInstance = {
                close: sinon.spy(),
                dismiss: sinon.spy(),
                result: {
                    then: sinon.spy(),
                },
            };

            controller = $controller(MonthModalController, {
                $location: $location,
                $uibModalInstance: modalInstance,
            });

            clock.restore();
        });
    });

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests call close modal', function () {
        controller.apply();
        assert(modalInstance.close.calledOnce);
    });

    it('tests call dismiss modal', function () {
        controller.close();
        assert(modalInstance.dismiss.calledOnce);
    });

    it('tests initiate years', function () {
        assert.equal(checkIfObjectExist(controller.years, 2014), false);
        assert.equal(checkIfObjectExist(controller.years, 2015), false);
        assert.equal(checkIfObjectExist(controller.years, 2016), false);
        assert.equal(checkIfObjectExist(controller.years, 2017), true);
    });

    it('tests select current year', function () {
        var fakeDate = new Date(2017, 9, 1);
        var clock = sinon.useFakeTimers(fakeDate.getTime());

        var expected = new Date().getFullYear();
        assert.equal(controller.selectedYear, expected);

        clock.restore();
    });

    it('tests select current month', function () {
        var fakeDate = new Date(2016, 9, 1);
        var clock = sinon.useFakeTimers(fakeDate.getTime());

        var expected = new Date().getMonth() + 1;
        assert.equal(controller.selectedMonth, expected);
        clock.restore();
    });

    it('tests select month', function () {
        var fakeDate = new Date(2016, 9, 1);
        var clock = sinon.useFakeTimers(fakeDate.getTime());
        var expected = new Date().getMonth() - 3;

        var currentYear = new Date().getFullYear();
        controller.selectedMonth = new Date().getMonth() - 3;
        controller.onSelectYear(currentYear);

        assert.equal(controller.selectedMonth, expected);
        clock.restore();
    });

    it('test display info message on invalid sdd navigation', function () {
        var fakeDate = new Date(2016, 9, 1);
        var clock = sinon.useFakeTimers(fakeDate.getTime());
        injectSDDController();

        assert.equal(controller.showMessage, true);

        clock.restore();
    });

    it('test change default date in invalid sdd navigation', function () {
        var fakeDate = new Date(2016, 9, 1);
        var clock = sinon.useFakeTimers(fakeDate.getTime());
        injectSDDController();

        assert.equal(controller.selectedYear, new Date().getFullYear());
        assert.equal(controller.selectedMonth, new Date().getMonth() + 1);

        clock.restore();
    });

    function checkIfObjectExist(objectArray, name) {
        for (var i = 0; i < objectArray.length; i++) {
            if (objectArray[i].name === name) {
                return true;
            }
        }
        return false;
    }

    function injectSDDController() {
        $location.path('service_delivery_dashboard');

        inject(function ($controller, _$location_) {
            controller = $controller(MonthModalController, {
                $location: $location,
                $uibModalInstance: modalInstance,
            });
        });
    }
});
