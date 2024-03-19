"use strict";
hqDefine("app_manager/js/apps_base", function () {
    $(function () {
        $('#deleted-app-modal').modal({
            backdrop: 'static',
            keyboard: false,
            show: true,
        }).on('hide.bs.modal', function () {
            window.location = hqImport('hqwebapp/js/initial_page_data').reverse('dashboard_default');
        });
        var previewApp = hqImport('app_manager/js/preview_app');
        previewApp.initPreviewWindow();

        $('.appmanager-content').fadeIn();
        $('.appmanager-loading').fadeOut();

        hqImport("hqwebapp/js/layout").setIsAppbuilderResizing(true);
    });
});
