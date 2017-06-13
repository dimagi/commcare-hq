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

    $(document).ajaxComplete(function(e, xhr, options) {
        if (/edit_form_attr/.test(options.url) ||
            /edit_module_attr/.test(options.url) ||
            /edit_module_detail_screens/.test(options.url) ||
            /edit_app_attr/.test(options.url) ||
            /edit_form_actions/.test(options.url) ||
            /edit_commcare_settings/.test(options.url) ||
            /patch_xform/.test(options.url)) {
            $(hqLayout.selector.publishStatus).fadeIn();
        }
    });
});
