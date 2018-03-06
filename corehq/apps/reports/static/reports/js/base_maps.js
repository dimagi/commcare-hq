/* globals ICON_PATH, load */
ICON_PATH = "";
hqDefine("reports/js/base_maps", function() {
    var done = false;

    $(document).ajaxComplete(function() {
        var $data = $(".base-maps-data");
        if ($data.length && !done) {
            var context = $data.data("context");
            ICON_PATH = $data.data("icon_path");
            if (ICON_PATH && context) {
                load(context, ICON_PATH);
                done = true;
            }
        }
    });
});
