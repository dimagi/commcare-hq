/* globals ICON_PATH, load */
ICON_PATH = hqImport("hqwebapp/js/initial_page_data.js").get('icon_path');
hqDefine("reports/js/base_maps.js", function() {
    var context = hqImport("hqwebapp/js/initial_page_data.js").get('context');

    $(function() {
        if (context) {
            load(context, ICON_PATH);
        }
    });
});
