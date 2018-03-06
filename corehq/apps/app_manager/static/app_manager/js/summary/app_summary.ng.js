(function(angular, undefined) {
    'use strict';

    var summaryModule = angular.module('summaryModule', [
        'ng.django.rmi',
        'ui.bootstrap',
    ]);

    summaryModule.constant('summaryConfig', {
        staticRoot: '/',
        vellumTypes: {},
        formNameMap: {},
        appLangs: [],
    });

    summaryModule.factory('utils', ['$location', 'summaryConfig', function($location, config) {
        function Utils() {
            var self = this;
            self.getTemplate = function(filename) {
                return config.staticRoot + 'app_manager/ng_partials/' + filename;
            };
            self.getIcon = function(type) {
                var vtype = config.vellumTypes[type];
                if (vtype) {
                    return vtype.icon_bs3;
                }
                return '';
            };
            self.translateName = function(names, target_lang, fallback) {
                fallback = fallback ? fallback : '[unknown]';
                if (!names) {
                    return fallback;
                }
                var langs = [target_lang].concat(config.appLangs),
                    firstLang = _(langs).find(function(lang) {
                        return names[lang];
                    });
                if (!firstLang) {
                    return fallback;
                }
                return names[firstLang] + (firstLang === target_lang ? '' : ' [' + firstLang + ']');
            };
            self.getModuleName = function(formId, target_lang) {
                var names = config.formNameMap[formId];
                if (names) {
                    return self.translateName(names.module_name, target_lang);
                }
                return formId;
            };
            self.getFormName = function(formId, target_lang) {
                var names = config.formNameMap[formId];
                if (names) {
                    return self.translateName(names.form_name, target_lang);
                }
                return formId;
            };
            self.getFormUrl = function(formId, target_lang) {
                var names = config.formNameMap[formId];
                if (names) {
                    return names.form_url;
                }
                return formId;
            };
            self.getModuleUrl = function(FormOrModuleId, target_lang) {
                var names = config.formNameMap[FormOrModuleId];
                if (names) {
                    return names.module_url;
                }
                return FormOrModuleId;
            };
            self.isActive = function(path) {
                return $location.path().substr(0, path.length) === path;
            };
        }
        return new Utils();
    }]);

    summaryModule.factory('_', function() {
        return window._; // assumes underscore has already been loaded on the page
    });

    summaryModule.factory('summaryDataService', ['$q', 'djangoRMI', function($q, djangoRMI) {
        var self = this,
            service = {};
        self.caseData = null;
        self.formData = null;

        service.getCaseData = function() {
            var deferred = $q.defer();

            if (self.caseData === null) {
                djangoRMI.get_case_data({}).success(function(data) {
                    self.caseData = data;
                    deferred.resolve(data);
                }).error(function() {
                    deferred.reject();
                });
            } else {
                deferred.resolve(self.caseData);
            }
            return deferred.promise;
        };

        service.getFormData = function() {
            var deferred = $q.defer();

            if (self.formData === null) {
                djangoRMI.get_form_data({}).success(function(data) {
                    self.formData = data;
                    deferred.resolve(data);
                }).error(function(error) {
                    deferred.resolve({
                        success: false,
                        error: error,
                    });
                });
            } else {
                deferred.resolve(self.formData);
            }
            return deferred.promise;
        };
        return service;
    }]);

    var controllers = {};
    controllers.FormController = function($scope, summaryDataService, summaryConfig, utils) {
        var self = this;

        $scope.loading = true;
        $scope.isActive = utils.isActive;
        $scope.modules = [];
        $scope.formSearch = {
            id: '',
        };
        $scope.moduleSearch = {
            id: '',
        };
        $scope.lang = 'en';
        $scope.showLabels = true;
        $scope.showCalculations = false;
        $scope.showRelevance = false;
        $scope.showConstraints = false;
        $scope.showComments = false;
        $scope.appLangs = summaryConfig.appLangs;
        $scope.getFormUrl = utils.getFormUrl;
        $scope.getModuleUrl = utils.getModuleUrl;
        $scope.formDownloadURL = summaryConfig.formDownloadURL;
        $scope.appDownloadURL = summaryConfig.appDownloadURL;
        $scope.appSettingsURL = summaryConfig.appSettingsURL;
        $scope.appHomeURL = summaryConfig.appHomeURL;
        $scope.appName = summaryConfig.appName;
        $scope.readOnly = summaryConfig.readOnly;

        self.init = function() {
            $scope.loading = true;
            summaryDataService.getFormData().then(function(data) {
                $scope.loading = false;
                self.updateView(data);
            }, function() {
                $scope.loading = false;
            });
        };

        self.updateView = function(data) {
            if (data.success) {
                $scope.modules = data.response;
            }
            if (data.errors) {
                $scope.errors = data.errors;
            }
            if (data.error) {
                $scope.error = data.error;
            }
        };

        $scope.filterList = function(module, form) {
            $scope.moduleSearch.id = module ? module.id : '';
            $scope.formSearch.id = form ? form.id : '';
        };

        $scope.moduleSelected = function(module) {
            return $scope.moduleSearch.id === module.id && !$scope.formSearch.id;
        };

        $scope.allSelected = function() {
            return !$scope.moduleSearch.id && !$scope.formSearch.id;
        };

        $scope.getIcon = utils.getIcon;

        $scope.getQuestionLabel = function(question) {
            return utils.translateName(question.translations, $scope.lang, question.label);
        };

        $scope.getFormModuleLabel = function(form_module) {
            return utils.translateName(form_module.name, $scope.lang);
        };

        $scope.getModuleFormIcon = function(form_module) {
            var formIcon = 'fa fa-file-o appnav-primary-icon';
            if (form_module.action_type === 'open') {
                formIcon = 'fcc fcc-app-createform appnav-primary-icon appnav-primary-icon-lg';
            } else if (form_module.action_type === 'close') {
                formIcon = 'fcc fcc-app-completeform appnav-primary-icon appnav-primary-icon-lg';
            } else if (form_module.action_type === 'update') {
                formIcon = 'fcc fcc-app-updateform appnav-primary-icon appnav-primary-icon-lg';
            }
            return formIcon;
        };

        $scope.getModuleIcon = function(form_module) {
            var moduleIcon = 'fa fa-folder-open';
            if (form_module.module_type === 'advanced') {
                moduleIcon = 'fa fa-flask';
            } else if (form_module.module_type === 'report') {
                moduleIcon = 'fa fa-bar-chart';
            } else if (form_module.module_type === 'shadow') {
                moduleIcon = 'fa fa-folder-open-o';
            } else if (!form_module.is_surveys) {
                moduleIcon = 'fa fa-bars';
            }
            return moduleIcon;
        };

        self.init();
    };

    controllers.CaseController = function($scope, $anchorScroll, $location, _,
        summaryDataService, summaryConfig, utils) {
        var self = this;

        $scope.caseTypes = [];
        $scope.hierarchy = {};
        $scope.loading = true;
        $scope.lang = 'en';
        $scope.typeSearch = null;
        $scope.isActive = utils.isActive;
        $scope.getFormName = utils.getFormName;
        $scope.getModuleName = utils.getModuleName;
        $scope.getFormUrl = utils.getFormUrl;
        $scope.getModuleUrl = utils.getModuleUrl;
        $scope.showConditions = true;
        $scope.showCalculations = true;
        $scope.showLabels = true;
        $scope.appLangs = summaryConfig.appLangs;
        $scope.caseDownloadURL = summaryConfig.caseDownloadURL;
        $scope.appDownloadURL = summaryConfig.appDownloadURL;
        $scope.appSettingsURL = summaryConfig.appSettingsURL;
        $scope.appHomeURL = summaryConfig.appHomeURL;
        $scope.appName = summaryConfig.appName;
        $scope.readOnly = summaryConfig.readOnly;

        $scope.filterCaseTypes = function(caseType) {
            $scope.typeSearch = caseType ? {
                'name': caseType,
            } : null;
        };

        $scope.hasErrors = function(caseTypeName) {
            var caseType = _.find($scope.caseTypes, function(caseType) {
                return caseType.name === caseTypeName;
            });
            return caseType ? caseType.has_errors : false;
        };

        $scope.gotoAnchor = function(caseType, property) {
            var newHash = caseType + ':' + property;
            if ($location.hash() !== newHash) {
                $location.hash(newHash);
            } else {
                $anchorScroll();
            }
        };

        self.init = function() {
            $scope.loading = true;
            summaryDataService.getCaseData().then(function(data) {
                $scope.loading = false;
                self.updateView(data);
            }, function() {
                $scope.loading = false;
            });
        };

        self.updateView = function(data) {
            if (data.success) {
                var response = data.response;
                $scope.caseTypes = response.case_types;
                $scope.hierarchy = response.type_hierarchy;
            }
        };

        self.init();
    };
    summaryModule.controller(controllers);

    summaryModule.directive('openerCloser', ['utils', function(utils) {
        return {
            restrict: 'E',
            templateUrl: '/opener_closer.html',
            scope: {
                forms: '=',
                lang: '=',
            },
            controller: function($scope) {
                $scope.getFormName = utils.getFormName;
            },
        };
    }]);

    summaryModule.directive('formQuestions', ['utils', function(utils) {
        return {
            restrict: 'E',
            templateUrl: '/form_questions.html',
            scope: {
                questions: '=',
                showConditions: '=',
                showCalculations: '=',
                showConstraints: '=',
                showLabels: '=',
                lang: '=',
            },
            controller: function($scope) {
                $scope.getIcon = utils.getIcon;
                $scope.getQuestionLabel = function(question) {
                    return utils.translateName(question.translations, $scope.lang, question.label);
                };
                $scope.getSelectOptionsLabel = function(option) {
                    return utils.translateName(option.translations, $scope.lang, option.label);
                };
            },
        };
    }]);
    summaryModule.directive('loading', function() {
        return {
            restrict: 'E',
            replace: true,
            templateUrl: '/loading.html',
            link: function(scope, element, attr) {
                scope.$watch('loading', function(val) {
                    if (val) {
                        $(element).show();
                    } else {
                        $(element).hide();
                    }
                });
            },
        };
    });

    summaryModule.directive('hierarchy', function() {
        return {
            restrict: "E",
            replace: true,
            scope: {
                hierarchy: '=',
                filterCaseTypes: '&',
                hasErrors: '&',
                typeSearch: '=',
            },
            templateUrl: '/hierarchy.html',
        };
    });

    summaryModule.directive('member', function($compile) {
        return {
            restrict: "E",
            replace: true,
            scope: {
                casetype: '=',
                hierarchy: '=',
                filterCaseTypes: '&',
                hasErrors: '&',
                typeSearch: '=',
            },
            templateUrl: '/hierarchy_member.html',
            link: function(scope, element, attrs) {
                var hierarchySt = '<hierarchy ' +
                    'hierarchy="hierarchy" ' +
                    'filter-case-types="filterCaseTypes({casetype: casetype})"' +
                    'has-errors="hasErrors({casetype: casetype})"' +
                    'type-search="typeSearch"' +
                    '></hierarchy>';
                if (angular.isObject(scope.hierarchy) && Object.getOwnPropertyNames(scope.hierarchy).length > 0) {
                    $compile(hierarchySt)(scope, function(cloned, scope) {
                        element.append(cloned);
                    });
                }
            },
        };
    });
}(window.angular));