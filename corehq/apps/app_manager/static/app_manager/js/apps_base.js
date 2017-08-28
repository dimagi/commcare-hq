/* globals hqImport, hqLayout */

$(function () {
    $('#deleted-app-modal').modal({
        backdrop: 'static',
        keyboard: false,
        show: true
    }).on('hide.bs.modal', function () {
        window.location = hqImport('hqwebapp/js/initial_page_data').reverse('default_app');
    });
    var previewApp = hqImport('app_manager/js/preview_app');
    previewApp.initPreviewWindow(hqLayout);

    $('.appmanager-content').fadeIn();
    $('.appmanager-loading').fadeOut();

    hqLayout.utils.setIsAppbuilderResizing(true);
});
