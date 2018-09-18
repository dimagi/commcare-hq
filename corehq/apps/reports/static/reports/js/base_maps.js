hqDefine("reports/js/base_maps", function () {
    var done = false;

    $(document).ajaxComplete(function () {
        var $data = $(".base-maps-data");
        if ($data.length && !done) {
            var context = $data.data("context"),
                iconPath = $data.data("icon_path");
            if (iconPath && context) {
                hqImport("reports/js/maps_utils").load(context, iconPath);
                done = true;
            }
        }
    });
});
