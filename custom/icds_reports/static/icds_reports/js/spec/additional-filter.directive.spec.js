/* global module, inject, chai, AdditionalFilterController, AdditionalModalController */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Additional Filter Controller', function () {

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

            controller = $controller(AdditionalFilterController, {
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

    it('tests get empty placeholder', function () {
        var result = controller.getPlaceholder();
        var expected = 'Additional Filter';

        assert.equal(expected, result);
    });
});

describe('Additional Modal Controller', function () {

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("genders", [
            {id: '', name: 'All'},
            {id: 'M', name: 'Male'},
            {id: 'F', name: 'Female'},
        ]);
        $provide.constant('ages', [
            {id: '', name: 'All'},
            {id: '6', name: '0-6 months'},
            {id: '12', name: '6-12 months'},
            {id: '24', name: '12-24 months'},
            {id: '36', name: '24-36 months'},
            {id: '48', name: '36-48 months'},
            {id: '60', name: '48-60 months'},
            {id: '72', name: '60-72 months'},
        ]);
        $provide.constant("userLocationId", null);
    }));

    var scope, modalInstance, controller, $uibModal, $location;

    beforeEach(function () {
        inject(function ($rootScope, $controller, _$uibModal_, _$location_, genders, ages) {
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

            $location.search('gender', 'M');
            $location.search('age', '0-6 months');
            $location.path('underweight_children/wasting');

            controller = $controller(AdditionalModalController, {
                $scope: scope,
                $uibModalInstance: modalInstance,
                $location: $location,
                filters: [],
                genders: genders,
                ages: ages,
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

    it('tests reset filters', function () {
        controller.selectedGender = "male";
        controller.selectedAge = "6";
        assert.equal(controller.selectedAge, '6');
        assert.equal(controller.selectedGender, 'male');

        controller.reset();
        assert.equal(controller.selectedAge, '');
        assert.equal(controller.selectedGender, '');
    });

    it('tests select gender', function () {
        var expected = 'M';
        assert.equal(controller.selectedGender, expected);
    });

    it('tests select age', function () {
        var expected = '0-6 months';
        assert.equal(controller.selectedAge, expected);
    });

    it('tests get path', function () {
        var expected = 6;
        assert.equal(controller.ages.length, expected);
    });

});