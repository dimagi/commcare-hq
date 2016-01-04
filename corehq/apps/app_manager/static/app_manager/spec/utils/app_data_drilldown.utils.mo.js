(function() {
    'use strict';

    window.AppDrill = {};

    window.AppDrill.mockBackendUrls = {
        GET_DRILLDOWN_VALUES: '/fake/app/drilldown/vals'
    };

    window.AppDrill.prepareTests = function () {
        beforeEach(function () {
            var drilldownApp = angular.module('ngtest.AppDataDrilldownApp', ['hq.app_data_drilldown']);
            drilldownApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
                djangoRMIProvider.configure({
                    get_app_data_drilldown_values: {
                        url: AppDrill.mockBackendUrls.GET_DRILLDOWN_VALUES,
                        headers: {
                            'DjNg-Remote-Method': 'get_app_data_drilldown_values'
                        },
                        method: 'auto'
                    }
                });
            }]);
            module('ngtest.AppDataDrilldownApp');
            // Kickstart the injectors previously registered with calls to angular.mock.module
            inject(function () {
            });
        });

        beforeEach(inject(function ($injector) {
            AppDrill.$rootScope = $injector.get('$rootScope');
            AppDrill.$httpBackend = $injector.get('$httpBackend');
            AppDrill.$interval = $injector.get('$interval');

            var $controller = $injector.get('$controller');
            AppDrill.createController = function () {
                AppDrill.currentScope = AppDrill.$rootScope.$new();
                return $controller('DrilldownToFormController', {
                    '$scope': AppDrill.currentScope
                });
            };
        }));
    };

    window.AppDrill.getCaseTypeResponse = function () {
        return {
            success: true,
                app_types: [
            {id: 'all', text: 'All Applications', data: {}},
            {id: 'deleted', text: 'Deleted Application', data: {}},
            {id: 'no_app', text: 'No Application', data: {}}
        ],
            apps_by_type: {
            deleted: [
                {id: 'app-deleted', text: 'App Deleted'}
            ],
                all: [
                {id: 'app-1', text: 'App 1'}
            ],
                no_app: [
                {id: '_unknown', text: 'Unknown App'}
            ],
                remote: [
                {id: 'app-remote', text: 'Remote App'}
            ]
        },
            case_types_by_app: {
                'app-deleted': [],
                    '_unknown': [],
                    'app-remote': [],
                    'app-1': [
                    {id: 'case', text: "Case"}
                ]
            },
            placeholders: {
                application: 'Select Application',
                    case_type: 'Select Case Type'
            }
        };
    };

    window.AppDrill.getSingleAppResponse = function () {
        return {
            success: true,
            app_types: [
                {id: 'all', text: 'All Applications', data: {}}
            ],
            apps_by_type: {
                deleted: [],
                all: [
                    {id: 'app-1', text: 'App 1'}
                ],
                no_app: [],
                remote: []
            },
            forms_by_app_by_module: {
                'app-1': {
                    '0': [
                        {
                            id: 'http://openrosa.org/formdesigner/app1-form1',
                            text: 'Questions',
                            data: {
                                app: {id: 'app-1', name: 'App 1'},
                                submissions: 11
                            }
                        }
                    ],
                    '1': [
                        {
                            id: 'http://openrosa.org/formdesigner/app1-form2',
                            text: 'Register',
                            data: {
                                app: {id: 'app-1', name: 'App 1'},
                                submissions: 0
                            }
                        },
                        {
                            id: 'http://openrosa.org/formdesigner/app1-form3',
                            text: 'Update',
                            data: {
                                app: {id: 'app-1', name: 'App 1'},
                                submissions: 5
                            }
                        }
                    ],
                    '_unknown': [
                        {
                            id: 'http://code.javarosa.org/devicereport',
                            text: 'http://code.javarosa.org/devicereport',
                            data: {
                                no_suggestions: true,
                                submissions: 1,
                                app: {id: 'app-1', name: 'App 1'}
                            }
                        }
                    ]
                }
            },
            modules_by_app: {
                'app-1': [
                    {id: 0, text: 'Questions Module'},
                    {id: 1, text: "Registration Module"},
                    {id: '_unknown', text: "Unknown Module"}
                ]
            },
            placeholders: {
                application: 'Select Application',
                module: 'Select Module',
                form: 'Select Form'
            }
        };
    };

    window.AppDrill.getMultiAppTypesResponse = function () {
        return {
            success: true,
            app_types: [
                {id: 'all', text: 'All Applications', data: {}},
                {id: 'deleted', text: 'Deleted Application', data: {}},
                {id: 'no_app', text: 'No Application', data: {}},
                {id: 'remote', text: 'Remote Application', data: {}}
            ],
            apps_by_type: {
                deleted: [
                    {id: 'app-deleted', text: 'App Deleted', data: {restoreUrl: '/fake/path/to/restore'}}
                ],
                    all: [
                    {id: 'app-1', text: 'App 1', data: {}}
                ],
                    no_app: [
                    {id: '_unknown', text: 'Unknown App', data: {}}
                ],
                    remote: [
                    {id: 'app-remote', text: 'Remote App', data: {}}
                ]
            },
            forms_by_app_by_module: {
                '_unknown': {
                    '_unknown': [
                        {
                            id: 'http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A',
                            text: 'http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A',
                            data: {
                                app: {id: ''},
                                has_app: false,
                                no_suggestions: true,
                                possiblities: [],
                                is_user_registration: false,
                                submissions: 1
                            }
                        },
                        {
                            id: 'http://openrosa.org/formdesigner/possible-matches',
                            text: 'http://openrosa.org/formdesigner/possible-matches',
                            data: {
                                app: {id: ''},
                                has_app: false,
                                duplicate: true,
                                no_suggestions: false,
                                possiblities: [
                                    {app: {name: 'Possible Match'}, app_deleted: false}
                                ],
                                is_user_registration: false,
                                submissions: 1
                            }
                        },
                        {
                            id: 'http://openrosa.org/formdesigner/possible-matches-registration',
                            text: 'http://openrosa.org/formdesigner/possible-matches-registration',
                            data: {
                                app: {id: ''},
                                has_app: false,
                                duplicate: true,
                                no_suggestions: false,
                                possiblities: [
                                    {app: {name: 'Possible Match 2'}, app_deleted: true}
                                ],
                                is_user_registration: true,
                                submissions: 1
                            }
                        },
                        {
                            id: 'http://openrosa.org/formdesigner/mislabeled',
                            text: 'http://openrosa.org/formdesigner/mislabeled',
                            data: {
                                app: {id: ''},
                                has_app: false,
                                duplicate: false,
                                no_suggestions: false,
                                possibilities: [],
                                app_copy: {app: {name: 'Copied App'}, app_deleted: true},
                                is_user_registration: true,
                                submissions: 1
                            }
                        },
                        {
                            id: 'http://openrosa.org/formdesigner/does-not-exist',
                            text: 'http://openrosa.org/formdesigner/does-not-exist',
                            data: {
                                app_does_not_exist: true,
                                app: {},
                                submissions: 1
                            }
                        }
                    ]
                },
                'app-1': {
                    '0': [
                        {
                            id: 'http://openrosa.org/formdesigner/app1-form1',
                            text: 'Questions',
                            data: {
                                app: {id: 'app-1', name: 'App 1'},
                                submissions: 11
                            }
                        }
                    ],
                        '1': [
                        {
                            id: 'http://openrosa.org/formdesigner/app1-form2',
                            text: 'Register',
                            data: {
                                app: {id: 'app-1', name: 'App 1'},
                                submissions: 0
                            }
                        },
                        {
                            id: 'http://openrosa.org/formdesigner/app1-form3',
                            text: 'Update',
                            data: {
                                app: {id: 'app-1', name: 'App 1'},
                                submissions: 5
                            }
                        }
                    ],
                        '_unknown': [
                        {
                            id: 'http://code.javarosa.org/devicereport',
                            text: 'http://code.javarosa.org/devicereport',
                            data: {
                                no_suggestions: true,
                                submissions: 1,
                                app: {id: 'app-1', name: 'App 1'}
                            }
                        }
                    ]
                },
                'app-deleted': {
                    '0': [
                        {
                            id: 'http://openrosa.org/formdesigner/app-deleted-form-1',
                            text: 'Form 1 App Deleted',
                            data: {
                                app: {id: 'app-deleted', name: 'Deleted App'},
                                submissions: 1
                            }
                        }
                    ]
                },
                'app-remote': {
                    '0': [
                        {
                            id: 'http://openrosa.org/formdesigner/remote-form',
                            text: 'Form 1 App Remote',
                            data: {
                                app: {id: 'app-remote', name: 'Remote App'},
                                submissions: 1
                            }
                        }
                    ]
                }
            },
            modules_by_app: {
                'app-1': [
                    {id: 0, text: 'Questions Module'},
                    {id: 1, text: "Registration Module"},
                    {id: '_unknown', text: "Unknown Module"}
                ],
                'app-deleted': [
                    {id: 0, text: 'App Deleted Module 1'}
                ],
                '_unknown': [
                    {id: '_unknown', text: 'Unknown Module'}
                ],
                'app-remote': [
                    {id: '_unknown', text: "Unknown Module"}
                ]
            },
            placeholders: {
                application: 'Select Application',
                module: 'Select Module',
                form: 'Select Form'
            }
        };
    };

})();
