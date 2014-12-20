(function (angular, undefined) {
    'use strict';

    var utils = {
        getUrl: function (config, prefix) {
            return config.staticRoot + prefix;
        },
        getTemplate: function (config, filename) {
            return config.staticRoot + 'app_manager/ng_partials/' + filename;
        },
        getIcon: function (config, type) {
            var vtype = config.vellumTypes[type];
            if (vtype) {
                return vtype.icon_bs3;
            }
            return ''
        },
        getFormName: function (config, formId, lang) {
            var name = config.formNameMap[formId];
            if (name) {
                return name.module_name[lang] + ' -> ' + name.form_name[lang];
            }
            return formId;
        }
    };

    var summaryModule = angular.module('summaryModule', [
        'ng.django.rmi'
    ]);

    summaryModule.constant('summaryConfig', {
        staticRoot: '/',
        vellumTypes: {},
        formNameMap: {}
    });

    var controllers = {};
    controllers.FormController = function ($scope, djangoRMI, summaryConfig) {
        var self = this;

        $scope.loading = true;

        $scope.getUrl = function (prefix) {
            return utils.getUrl(summaryConfig, prefix);
        };
    };

    controllers.CaseController = function ($scope, djangoRMI, summaryConfig) {
        var self = this;

        $scope.caseTypes = [];
        $scope.loading = true;
        $scope.lang = 'en';
        $scope.typeSearch = {name: ''};

        self.init = function (attrs) {
            self.refreshData();
        };

        self.refreshData = function () {
            $scope.loading = true;
            djangoRMI.get_case_data({
            }).success(function (data) {
                $scope.loading = false;
                self.updateView(data);
            }).error(function () {
                $scope.loading = false;
            });
        };

        self.updateView = function (data) {
            if (data.success) {
                var response = data.response;
                $scope.caseTypes = response.case_types;
            }
        };

        $scope.getFormName = function (formId) {
            return utils.getFormName(summaryConfig, formId, $scope.lang);
        };

        $scope.getUrl = function (prefix) {
            return utils.getUrl(summaryConfig, prefix);
        };

        $scope.filterCaseTypes = function (caseType) {
            $scope.typeSearch.name = caseType;
        };

        self.init();
    };
    summaryModule.controller(controllers);

    var directives = {};
    directives.openerCloser = function (summaryConfig) {
        return {
            restrict: 'E',
            templateUrl: utils.getTemplate(summaryConfig, 'opener_closer.html'),
            scope: {
                title: '@',
                forms: '=',
                lang: '='
            },
            controller: function ($scope) {
                $scope.getFormName = function (formId) {
                    return utils.getFormName(summaryConfig, formId, $scope.lang);
                };
            }
        }
    };

    directives.formQuestions = function (summaryConfig) {
        return {
            restrict: 'E',
            templateUrl: utils.getTemplate(summaryConfig, 'form_questions.html'),
            scope: {
                questions: '='
            },
            controller: function ($scope) {
                $scope.getIcon = function (questionType) {
                    return utils.getIcon(summaryConfig, questionType);
                };
            }
        }
    };
    summaryModule.directive(directives);

}(window.angular));