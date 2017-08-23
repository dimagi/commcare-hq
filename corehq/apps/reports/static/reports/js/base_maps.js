/* globals ICON_PATH, load */
ICON_PATH = hqImport("hqwebapp/js/initial_page_data").get('icon_path');
hqDefine("reports/js/base_maps", function() {
    var context = hqImport("hqwebapp/js/initial_page_data").get('context');

    $(function() {
        if (context) {
            load(context, ICON_PATH);
        }
    });
});
