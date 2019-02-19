/* globals leafletImage */
hqDefine("ewsghana/js/map", function() {
    function load(context, iconPath) {
        L.Icon.Default.imagePath = iconPath;
        var map = mapsInit(context);

        var resize = function() {
            hqImport("reports/js/maps_utils").setMapHeight(map);
        };
        $(window).resize(resize);
        var $reportFiltersAccordion = $('#reportFiltersAccordion');
        $reportFiltersAccordion.on('shown', resize);
        $reportFiltersAccordion.on('hidden', resize);
        resize();
        return map;
    }

    $(function() {
        var baseMapsData = $(".base-maps-data").data(),
            context = baseMapsData.context,
            iconPath = baseMapsData.icon_path;
        if (context !== '') {
            var map = load(context, iconPath);
            $('#export-jpg').click(function() {
                var $button = $(this);
                var text = $button.text();
                $button.text('Loading...');
                $button.prop('disabled', true);
                leafletImage(map, function(err, canvas) {
                    var data = canvas.toDataURL("image/jpeg", 1);
                    var a = document.createElement('a');
                    a.href = data;
                    a.download = 'map.jpg';
                    $('body').append(a);
                    a.click();
                    a.remove();
                    $button.text(text);
                    $button.prop('disabled', false);
                });
            });
        }
    });
});
