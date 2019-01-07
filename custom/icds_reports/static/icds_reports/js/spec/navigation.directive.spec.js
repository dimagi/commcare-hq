/* global module, inject, chai */
"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('Navigation Directive', function () {

    pageData.registerUrl('icds-ng-template', 'template');
    pageData.registerUrl('icds_locations', 'icds_locations');

    var $rootScope, $compile, $httpBackend, controller;

    var myScope;

    beforeEach(module('icdsApp', function ($provide) {
        $provide.constant("stateLevelAccess", false);
        $provide.constant("haveAccessToAllLocations", false);
        $provide.constant("haveAccessToFeatures", false);
    }));

    beforeEach(inject(function (_$rootScope_, _$compile_, _$httpBackend_) {
        $compile = _$compile_;
        $httpBackend = _$httpBackend_;
        $rootScope = _$rootScope_.$new();

        $httpBackend.expectGET('template').respond(200, '<div></div>');
        var element = window.angular.element("<navigation></navigation>");
        var compiled = $compile(element)($rootScope);

        $httpBackend.flush();
        $rootScope.$digest();
        controller = compiled.controller("navigation", {$scope: $rootScope});
        myScope = element.isolateScope();
    }));

    it('tests instantiate the controller properly', function () {
        chai.expect(controller).not.to.be.a('undefined');
    });

    it('tests get empty page path', function () {
        var result = myScope.goToStep("test", {});
        var expected = "#/test";
        assert.equal(result, expected);
    });

    it('tests get page path with one arguments', function () {
        var result = myScope.goToStep("test", {'one': 1});

        var expected = "#/test?one=1&";
        assert.equal(result, expected);
    });

    it('tests get page path with two arguments', function () {
        var result = myScope.goToStep("test", {'one': 1, 'two': 2});

        var expected = "#/test?one=1&two=2&";
        assert.equal(result, expected);
    });
});