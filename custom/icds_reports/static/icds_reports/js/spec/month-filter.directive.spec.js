/* global module, inject, _, moment, chai, MonthFilterController, MonthModalController */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Month filter controller', function () {

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

    it('should instantiate the controller properly', function () {
        var expect = chai.expect;
        expect(controller).not.to.be.a('undefined');
    });

    it('should call open modal', function () {
        var expect = chai.expect;
        var open = sinon.spy($uibModal, 'open');
        controller.open();
        expect(open).to.have.been.called;
    });

    it('should get placeholder', function () {
        var today = moment('2015-10-19').toDate();
        var clock = sinon.useFakeTimers(today.getTime());

        var result = controller.getPlaceholder();
        var expected = 'October 2015';

        assert.equal(expected, result);

        clock.restore();
    });
});

describe('Month modal controller', function () {

    beforeEach(module('icdsApp'));

    var scope, modalInstance, controller

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

    it('should instantiate the controller properly', function () {
        var expect = chai.expect;
        expect(controller).not.to.be.a('undefined');
    });

    it('should call close modal', function () {
        var expect = chai.expect;
        controller.apply();
        expect(modalInstance.close).to.have.been.called;
    });

    it('should call dismiss modal', function () {
        var expect = chai.expect;
        controller.close();
        expect(modalInstance.dismiss).to.have.been.called;
    });

    it('should initiate years', function () {
        assert.equal(checkIfObjectExist(controller.years, 2014), true);
        assert.equal(checkIfObjectExist(controller.years, 2015), true);
        assert.equal(checkIfObjectExist(controller.years, 2016), true);
        assert.equal(checkIfObjectExist(controller.years, 2017), true);
    });

    it('should select current year', function () {
        var expected = new Date().getFullYear();
        assert.equal(controller.selectedYear, expected);
    });

    it('should select current month', function () {
        var expected = new Date().getMonth() + 1;
        assert.equal(controller.selectedMonth, expected);
    });

    it('should select month', function () {
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