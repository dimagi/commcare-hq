/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');


describe('Kpi Directive', function () {

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
        var element = window.angular.element("<kpi></kpi>");

        var compiled = $compile(element)($scope);

        $httpBackend.flush();
        $scope.$digest();
        controller = compiled.controller("kpi");
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests get empty page path', function () {
        var result = controller.goToStep("test");
        var expected = "#/test";
        assert.equal(result, expected);
    });

    it('tests get page path with one arguments', function () {
        $location.search('one', 1);
        var result = controller.goToStep("test");

        var expected = "#/test?one=1&";
        assert.equal(result, expected);
    });

    it('tests get page path with two arguments', function () {
        $location.search('one', 1);
        $location.search('two', 2);
        var result = controller.goToStep("test");

        var expected = "#/test?one=1&two=2&";
        assert.equal(result, expected);
    });

    it('tests not shows percent info', function () {
        var expected = false;
        var result = controller.showPercentInfo();
        assert.equal(result, expected);
    });

    it('tests shows percent info from month parameter', function () {
        $location.search('month', new Date().getMonth());
        var expected = true;

        var result = controller.showPercentInfo();
        assert.equal(result, expected);
    });

    it('tests not shows percent info from wrong month parameter', function () {
        $location.search('month', new Date().getMonth() + 1);
        var expected = false;

        var result = controller.showPercentInfo();
        assert.equal(result, expected);
    });

    it('tests shows percent info from year parameter', function () {
        $location.search('year', new Date().getFullYear() + 1);
        var expected = true;

        var result = controller.showPercentInfo();
        assert.equal(result, expected);
    });

    it('tests not shows percent info from wrong year parameter', function () {
        $location.search('year', new Date().getFullYear());
        var expected = false;

        var result = controller.showPercentInfo();
        assert.equal(result, expected);
    });
});