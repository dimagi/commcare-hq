hqDefine("app_manager/js/nav_menu_media", function() {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
        _.each(initial_page_data("nav_menu_media_specifics"), function(item) {
            var initNavMenuMedia = hqImport('app_manager/js/app_manager_media').initNavMenuMedia;
            initNavMenuMedia(
                item.qualifier || "",
                item.menu_refs.image || "",
                item.menu_refs.audio || "",
                initial_page_data("multimedia_object_map"),
                item.default_file_name
            );
        });
    });
});
