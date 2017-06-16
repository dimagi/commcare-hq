/* globals hqLayout */

$(function () {
    var v2 = COMMCAREHQ.toggleEnabled('APP_MANAGER_V2');

    $('#deleted-app-modal').modal({
        backdrop: 'static',
        keyboard: false,
        show: true
    }).on('hide.bs.modal', function () {
        window.location = hqImport('hqwebapp/js/urllib.js').reverse('default_app');
    });
    if (hqImport('hqwebapp/js/initial_page_data.js').get('show_live_preview') || v2) {
        var previewApp = hqImport('app_manager/js/preview_app.js');
        previewApp.initPreviewWindow(hqLayout);
    }

    $('.appmanager-content').fadeIn();
    $('.appmanager-loading').fadeOut();

    if (v2) {
        hqLayout.utils.setIsAppbuilderResizing(true);
    }
});
