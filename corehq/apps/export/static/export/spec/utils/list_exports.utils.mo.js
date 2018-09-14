(function () {
    'use strict';

    window.ListExportsTestData = {
        exportWithFileData: {
            downloadUrl: '/a/test-exports/data/export/custom/form/download',
            emailedExport: {
                index: [
                    'test-exports',
                    'http://openrosa.org/formdesigner/11FAC65A-F2CD-427F-A870-CF126336AAB5',
                    'uuid-exportWithFileData',
                ],
                fileData: {
                    downloadUrl: '/a/test-exports/reports/export/saved/download/uuid-file/?group_export_id=uuid-group-exportWithFileData',
                    size: '207 bytes',
                    showExpiredWarning: false,
                    lastUpdated: '3 weeks, 3 days ago',
                    fileId: 'uuid-file',
                },
                groupId: 'uuid-group-exportWithFileData',
                hasFile: true,
                taskStatus: {
                    percentComplete: 0,
                    inProgress: false,
                    success: false,
                },
            },
            name: "Test Export With File Data",
            addedToBulk: false,
            editUrl: '/a/test-exports/export/custom/form/edit',
            isDeid: false,
            id: 'uuid-exportWithFileData',
            formname: 'Test Export With File Data',
            exportType: 'form',
            isAutoRebuildEnabled: true,
        },
        exportDeId: {
            downloadUrl: '/a/test-exports/data/export/custom/form/download',
            emailedExport: null,
            name: "Test Export De-Id",
            addedToBulk: false,
            editUrl: '/a/test-exports/export/custom/form/edit',
            isDeid: true,
            id: 'uuid-exportDeId',
            formname: 'Test Export De-Id',
            exportType: 'form',
            isAutoRebuildEnabled: true,
        },
        exportSimple: {
            downloadUrl: '/a/test-exports/data/export/custom/form/download',
            emailedExport: null,
            name: "Test Export Simple",
            addedToBulk: false,
            editUrl: '/a/test-exports/export/custom/form/edit',
            isDeid: false,
            id: 'uuid-exportSimple',
            formname: 'Test Export Simple',
            exportType: 'form',
            isAutoRebuildEnabled: true,
        },
    };

})();
