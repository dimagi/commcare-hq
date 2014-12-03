(function (angular, undefined) {
   'use strict';
    // module ccpublic.home
    var home = angular.module('ccpublic.home', []);

    home.constant('homeConfig', {
        caseTypes: [],
        defaultCaseType: ''
    });

    var homeControllers = {};
    homeControllers.CaseTypeCtrl = function ($scope, homeConfig) {
        var allCaseTypes = _.union([homeConfig.defaultCaseType], homeConfig.caseTypes);
        var _createCaseTypeObj = function (ct) {
            return {
                name: ct,
                value: ct
            };
        };
        var caseTypes = _(allCaseTypes).map(_createCaseTypeObj);
        $scope.caseTypes = caseTypes;
        $scope.selectedCaseType = _createCaseTypeObj(homeConfig.defaultCaseType);
    };

    // load controllers
    home.controller('CaseTypeCtrl', homeControllers.CaseTypeCtrl);

}(window.angular));
