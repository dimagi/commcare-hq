hqDefine("app_manager/js/nav_menu_media", [
    "jquery",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/app_manager_media",
], function (
    $,
    _,
    initialPageData,
    appManagerMedia,
) {
    $(function () {
        _.each(initialPageData.get("nav_menu_media_specifics"), function (item) {
            appManagerMedia.initNavMenuMedia(
                item.qualifier || "",
                item.menu_refs.image || "",
                item.menu_refs.audio || "",
                initialPageData.get("multimedia_object_map"),
                item.default_file_name,
            );
        });
    });
});
