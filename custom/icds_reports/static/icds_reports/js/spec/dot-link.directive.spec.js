/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Dot Link Directive', function () {

    var $scope, $compile, $location, controller, $httpBackend;

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('icds_locations', 'icds_locations');

    beforeEach(module('icdsApp'));

    beforeEach(inject(function ($rootScope, _$compile_, _$location_, _$httpBackend_) {
        $compile = _$compile_;
        $httpBackend = _$httpBackend_;
        $scope = $rootScope.$new();
        $location = _$location_;

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        var element = window.angular.element("<dot-link></dot-link>");

        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller("dotLink");
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests active', function () {
        controller.route  = '/test';
        $location.path('test');
        var result = controller.isActive();

        var expected = true;
        assert.equal(result, expected);
    });

    it('tests not active', function () {
        controller.route  = '/test1234';
        $location.path('test');
        var result = controller.isActive();

        var expected = false;
        assert.equal(result, expected);
    });

    it('tests not active when location not set', function () {
        var result = controller.isActive();
        var expected = false;
        assert.equal(result, expected);
    });

    it('tests on click', function () {
        controller.route  = '/test';
        controller.onClick();
        var result = $location.path();

        var expected = '/test';
        assert.equal(result, expected);
    });
});