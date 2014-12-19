(function (angular, undefined) {
    'use strict';

    var utils = {
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

    var summaryModule = angular.module('SummaryModule', ['ng.django.rmi']);

    summaryModule.constant('summaryConfig', {
        staticRoot: '/',
        vellumTypes: {},
        formNameMap: {}
    });

    var controllers = {};
    controllers.CaseController = function ($scope, djangoRMI, summaryConfig) {
        var self = this;

        $scope.caseTypes = [];
        $scope.loading = false;
        $scope.lang = 'en';

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