(function() {
    'use strict';

    window.DnldExpData = {
        simpleFormExport: {
            domain: 'test-export',
            xmlns: 'http://openrosa.org/formdesigner/11FAC65A-F2CD-427F-A870-CF126336AAB5',
            name: 'Simple Form Export',
            export_type: 'form',
            sheet_name: 'Simple Form Export',
            export_id: 'uuid-simpleFormExport',
            edit_url: '/a/test-export/data/export/custom/form/edit/uuid-simpleFormExport/',
            filename: 'simpleformexport'
        },
        groupList: [
            {
                test: 'A Group',
                id: 'uuid-agroup'
            }
        ],
        getPollResponseProgress: function (downloadId) {
            return {
                allow_dropbox_sync: false,
                custom_message: null,
                download_id: downloadId,
                has_file: false,
                is_alive: null,
                is_poll_successful: true,
                is_ready: false,
                progress: {
                    current: 1,
                    error: false,
                    error_message: "",
                    percent: 10,
                    total: 10
                }
            };
        },
        getPollResponseCeleryError: function (downloadId) {
            return {
                allow_dropbox_sync: false,
                custom_message: null,
                download_id: downloadId,
                has_file: false,
                is_alive: null,
                is_poll_successful: false,
                is_ready: false,
                progress: {
                    current: 1,
                    error: false,
                    error_message: "",
                    percent: 10,
                    total: 10
                }
            };
        },
        getPollResponseProgressError: function (downloadId) {
            return {
                allow_dropbox_sync: false,
                custom_message: null,
                download_id: downloadId,
                has_file: false,
                is_alive: null,
                is_poll_successful: true,
                is_ready: false,
                progress: {
                    current: 1,
                    error: true,
                    error_message: "error during progress",
                    percent: 10,
                    total: 10
                }
            };
        },
        getPollResponseError: function (downloadId) {
            return {
                allow_dropbox_sync: false,
                custom_message: null,
                download_id: downloadId,
                has_file: false,
                is_alive: null,
                is_poll_successful: false,
                is_ready: false,
                progress: {
                    current: 1,
                    error: false,
                    error_message: "",
                    percent: 10,
                    total: 10
                },
                error: "error during poll response"
            };
        },
        getPollResponseSuccess: function (downloadId) {
            return {
                allow_dropbox_sync: false,
                custom_message: null,
                download_id: downloadId,
                download_url: '/download/fake/file/' + downloadId,
                dropbox_url: '/download/dropbox/file/' + downloadId,
                has_file: true,
                is_alive: null,
                is_poll_successful: true,
                is_ready: true,
                progress: {
                    current: null,
                    error: false,
                    error_message: "",
                    percent: null,
                    total: null
                },
                result: null
            };
        },
        mockBackendUrls: {
            HAS_MULTIMEDIA: '/fake/exports/multimedia/check',
            GET_GROUP_OPTIONS: '/fake/exports/groups',
            PREPARE_CUSTOM_EXPORT: '/fake/exports/prepare',
            PREPARE_FORM_MULTIMEDIA: '/fake/exports/prepare/multimedia',
            POLL_EXPORT_DOWNLOAD: '/fake/exports/poll/download'
        }
    };

    window.DnldExpData.prepareTests = function () {
        beforeEach(function () {
            var downloadExportApp = angular.module('ngtest.DownloadExportApp', ['hq.download_export']);
            downloadExportApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
                djangoRMIProvider.configure({
                    has_multimedia: {
                        url: DnldExpData.mockBackendUrls.HAS_MULTIMEDIA,
                        headers: {
                            'DjNg-Remote-Method': 'has_multimedia'
                        },
                        method: 'auto'
                    },
                    get_group_options: {
                        url: DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS,
                        headers: {
                            'DjNg-Remote-Method': 'get_group_options'
                        },
                        method: 'auto'
                    },
                    prepare_custom_export: {
                        url: DnldExpData.mockBackendUrls.PREPARE_CUSTOM_EXPORT,
                        headers: {
                            'DjNg-Remote-Method': 'prepare_custom_export'
                        },
                        method: 'auto'
                    },
                    prepare_form_multimedia: {
                        url: DnldExpData.mockBackendUrls.PREPARE_FORM_MULTIMEDIA,
                        headers: {
                            'DjNg-Remote-Method': 'prepare_form_multimedia'
                        },
                        method: 'auto'
                    },
                    poll_custom_export_download: {
                        url: DnldExpData.mockBackendUrls.POLL_EXPORT_DOWNLOAD,
                        headers: {
                            'DjNg-Remote-Method': 'poll_custom_export_download'
                        },
                        method: 'auto'
                    }
                });
            }]);
            module('ngtest.DownloadExportApp');
            // Kickstart the injectors previously registered with calls to angular.mock.module
            inject(function () {
            });
        });

        beforeEach(inject(function ($injector) {
            DnldExpData.$rootScope = $injector.get('$rootScope');
            DnldExpData.$httpBackend = $injector.get('$httpBackend');
            DnldExpData.$interval = $injector.get('$interval');
            DnldExpData.exportDownloadService = $injector.get('exportDownloadService');
        }));
    };

    window.DnldExpData.prepareDownloadController = function () {
        beforeEach(inject(function ($injector) {
            var $controller = $injector.get('$controller');
            DnldExpData.createController = function (exportList, checkForMultimedia) {
                DnldExpData.currentScope = DnldExpData.$rootScope.$new();
                return $controller('DownloadExportFormController', {
                    '$scope': DnldExpData.currentScope,
                    checkForMultimedia: checkForMultimedia || false,
                    exportList: exportList
                });
            };

        }));
    };



    window.DnldExpData.prepareDownloadProgressController = function () {
        beforeEach(inject(function ($injector) {
            var $controller = $injector.get('$controller');
            DnldExpData.createProgressController = function () {
                DnldExpData.currentScope = DnldExpData.$rootScope.$new();
                return $controller('DownloadProgressController', {
                    '$scope': DnldExpData.currentScope
                });
            };

        }));
    };

    window.DnldExpData.prepareBackends = function () {
        beforeEach(function () {
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.HAS_MULTIMEDIA)
                .respond({
                    success: true,
                    hasMultimedia: true
                });
            DnldExpData.$httpBackend
                .when('POST', DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS)
                .respond({
                    success: true,
                    groups: DnldExpData.groupList
                });
            DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.HAS_MULTIMEDIA);
            DnldExpData.$httpBackend.expectPOST(DnldExpData.mockBackendUrls.GET_GROUP_OPTIONS);
        });

        afterEach(function() {
            DnldExpData.$httpBackend.verifyNoOutstandingExpectation();
            DnldExpData.$httpBackend.verifyNoOutstandingRequest();
        });
    };
})();
