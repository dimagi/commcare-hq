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
        chai.expect(open).to.have.been.called;
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

    var scope, modalInstance, controller;

    beforeEach(function () {
        inject(function ($rootScope, $controller) {
            scope = $rootScope.$new();

            modalInstance = {
                close: sinon.spy(),
                dismiss: sinon.spy(),
                result: {
                    then: sinon.spy(),
                },
            };

            controller = $controller(MonthModalController, {
                $scope: scope,
                $uibModalInstance: modalInstance,
            });
        });
    });

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests call close modal', function () {
        controller.apply();
        chai.expect(modalInstance.close).to.have.been.called;
    });

    it('tests call dismiss modal', function () {
        controller.close();
        chai.expect(modalInstance.dismiss).to.have.been.called;
    });

    it('tests initiate years', function () {
        assert.equal(checkIfObjectExist(controller.years, 2014), true);
        assert.equal(checkIfObjectExist(controller.years, 2015), true);
        assert.equal(checkIfObjectExist(controller.years, 2016), true);
        assert.equal(checkIfObjectExist(controller.years, 2017), true);
    });

    it('tests select current year', function () {
        var expected = new Date().getFullYear();
        assert.equal(controller.selectedYear, expected);
    });

    it('tests select current month', function () {
        var expected = new Date().getMonth() + 1;
        assert.equal(controller.selectedMonth, expected);
    });

    it('tests select month', function () {
        var expected = new Date().getMonth() - 3;

        var currentYear = new Date().getFullYear();
        controller.selectedMonth = new Date().getMonth() - 3;
        controller.onSelectYear(currentYear);

        assert.equal(controller.selectedMonth, expected);
    });

    function checkIfObjectExist(objectArray, name) {
        for (var i = 0; i < objectArray.length; i++) {
            if (objectArray[i].name === name) {
                return true;
            }
        }
        return false;
    }
});