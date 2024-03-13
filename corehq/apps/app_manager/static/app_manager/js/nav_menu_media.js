hqDefine("app_manager/js/nav_menu_media", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        _.each(initialPageData.get("nav_menu_media_specifics"), function (item) {
            var initNavMenuMedia = hqImport('app_manager/js/app_manager_media').initNavMenuMedia;
            initNavMenuMedia(
                item.qualifier || "",
                item.menu_refs.image || "",
                item.menu_refs.audio || "",
                initialPageData.get("multimedia_object_map"),
                item.default_file_name
            );
        });
    });
});
