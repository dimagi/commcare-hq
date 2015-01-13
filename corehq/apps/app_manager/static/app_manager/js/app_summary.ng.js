(function (angular, undefined) {
    'use strict';

    var summaryModule = angular.module('summaryModule', [
        'ng.django.rmi'
    ]);

    summaryModule.constant('summaryConfig', {
        staticRoot: '/',
        vellumTypes: {},
        formNameMap: {}
    });

    summaryModule.factory('utils', ['$location', 'summaryConfig', function ($location, config) {
        return {
            getTemplate: function (filename) {
                return config.staticRoot + 'app_manager/ng_partials/' + filename;
            },
            getIcon: function (type) {
                var vtype = config.vellumTypes[type];
                if (vtype) {
                    return vtype.icon_bs3;
                }
                return '';
            },
            getFormName: function (formId, lang) {
                var name = config.formNameMap[formId];
                if (name) {
                    return name.module_name[lang] + ' -> ' + name.form_name[lang];
                }
                return formId;
            },
            isActive: function (path) {
                return $location.path().substr(0, path.length) === path;
            }
        };
    }]);

    summaryModule.factory('summaryDataService', ['$q', 'djangoRMI', function ($q, djangoRMI) {
        var self = this,
            service = {};
        self.caseData = null;
        self.formData = null;

        service.getCaseData = function () {
            var deferred = $q.defer();

            if (self.caseData === null) {
                djangoRMI.get_case_data({}).success(function (data) {
                    self.caseData = data;
                    deferred.resolve(data);
                }).error(function () {
                    deferred.reject();
                });
            } else {
                deferred.resolve(self.caseData);
            }
            return deferred.promise;
        };

        service.getFormData = function () {
            var deferred = $q.defer();

            if (self.formData === null) {
                djangoRMI.get_form_data({}).success(function (data) {
                    self.formData = data;
                    deferred.resolve(data);
                }).error(function () {
                    deferred.reject();
                });
            } else {
                deferred.resolve(self.formData);
            }
            return deferred.promise;
        };
        return service;
    }]);

    var controllers = {};
    controllers.FormController = function ($scope, summaryDataService, summaryConfig, utils) {
        var self = this;

        $scope.loading = true;
        $scope.isActive = utils.isActive;
        $scope.modules = [];
        $scope.formSearch = {name: ''};
        $scope.moduleSearch = {name: ''};

        self.init = function () {
            $scope.loading = true;
            summaryDataService.getFormData().then(function (data) {
                $scope.loading = false;
                self.updateView(data);
            }, function () {
                $scope.loading = false;
            });
        };

        self.updateView = function (data) {
            if (data.success) {
                $scope.modules = data.response;
            }
        };

        $scope.filterList = function (module, form) {
            $scope.moduleSearch.name = module;
            $scope.formSearch.name = form;
        };

        $scope.getIcon = utils.getIcon;

        self.init();
    };

    controllers.CaseController = function ($scope, summaryDataService, summaryConfig, utils) {
        var self = this;

        $scope.caseTypes = [];
        $scope.hierarchy = {};
        $scope.loading = true;
        $scope.lang = 'en';
        $scope.typeSearch = {name: ''};
        $scope.isActive = utils.isActive;
        $scope.getFormName = utils.getFormName;

        $scope.filterCaseTypes = function (caseType) {
            $scope.typeSearch.name = caseType;
        };

        self.init = function () {
            $scope.loading = true;
            summaryDataService.getCaseData().then(function (data) {
                $scope.loading = false;
                self.updateView(data);
            }, function () {
                $scope.loading = false;
            });
        };

        self.updateView = function (data) {
            if (data.success) {
                var response = data.response;
                $scope.caseTypes = response.case_types;
                $scope.hierarchy = response.type_hierarchy;
            }
        };

        self.init();
    };
    summaryModule.controller(controllers);

    summaryModule.directive('openerCloser', ['utils', function (utils) {
        return {
            restrict: 'E',
            templateUrl: '/opener_closer.html',
            scope: {
                forms: '=',
                lang: '='
            },
            controller: function ($scope) {
                $scope.getFormName = utils.getFormName;
            }
        };
    }]);

    summaryModule.directive('formQuestions', ['utils', function (utils) {
        return {
            restrict: 'E',
            templateUrl: '/form_questions.html',
            scope: {
                questions: '='
            },
            controller: function ($scope) {
                $scope.getIcon = utils.getIcon;
            }
        };
    }]);
    summaryModule.directive('loading', function () {
        return {
            restrict: 'E',
            replace: true,
            templateUrl: '/loading.html',
            link: function (scope, element, attr) {
                scope.$watch('loading', function (val) {
                    if (val) {
                        $(element).show();
                    } else {
                        $(element).hide();
                    }
                });
            }
        };
    });

    summaryModule.directive('hierarchy', function () {
        return {
            restrict: "E",
            replace: true,
            scope: {
                hierarchy: '=',
                filterCaseTypes: '&',
                typeSearch: '='
            },
            templateUrl: '/hierarchy.html'
        };
    });

    summaryModule.directive('member', function ($compile) {
        return {
            restrict: "E",
            replace: true,
            scope: {
                casetype: '=',
                hierarchy: '=',
                filterCaseTypes: '&',
                typeSearch: '='
            },
            templateUrl: '/hierarchy_member.html',
            link: function (scope, element, attrs) {
                var hierarchySt = '<hierarchy ' +
                    'hierarchy="hierarchy" ' +
                    'filter-case-types="filterCaseTypes({casetype: casetype})"' +
                    'type-search="typeSearch"' +
                    '></hierarchy>';
                if (angular.isObject(scope.hierarchy)) {
                    $compile(hierarchySt)(scope, function(cloned, scope)   {
                        element.append(cloned);
                    });
                }
            }
        };
    });
}(window.angular));