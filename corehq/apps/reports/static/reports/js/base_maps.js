hqDefine("reports/js/base_maps.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    CONTEXT = initial_page_data('context');
    ICON_PATH = initial_page_data('icon_path');
    MIN_HEIGHT = 300; //px

    $(function() {
        if (CONTEXT) {
            load(CONTEXT, ICON_PATH);   // from maps_utils.js
        }
    });
});
