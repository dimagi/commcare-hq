hqDefine("app_manager/js/apps_base", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/preview_app",
    "hqwebapp/js/layout",
    "jquery-ui/ui/widgets/sortable",     // TODO: test sortables, also only include for modules that use them?
    "jquery-textchange/jquery.textchange",
    "langcodes/js/langcodes",   // TODO: is this one necessary?
    "commcarehq",
], function (
    $,
    initialPageData,
    previewApp,
    layout,
) {
    $(function () {
        $('#deleted-app-modal').modal({
            backdrop: 'static',
            keyboard: false,
            show: true,
        }).on('hide.bs.modal', function () {
            window.location = initialPageData.reverse('dashboard_default');
        });
        previewApp.initPreviewWindow();

        $('.appmanager-content').fadeIn();
        $('.appmanager-loading').fadeOut();

        layout.setIsAppbuilderResizing(true);
    });
});
