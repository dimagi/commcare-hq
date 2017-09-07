/* globals ICON_PATH, leafletImage */
ICON_PATH = hqImport("hqwebapp/js/initial_page_data").get('icon_path');
hqDefine("ewsghana/js/map", function() {
    var context = hqImport("hqwebapp/js/initial_page_data").get('context');

    function load(context, iconPath) {
        L.Icon.Default.imagePath = iconPath;
        var map = mapsInit(context);

        var resize = function() {
            setMapHeight(map);
        };
        $(window).resize(resize);
        var $reportFiltersAccordion = $('#reportFiltersAccordion');
        $reportFiltersAccordion.on('shown', resize);
        $reportFiltersAccordion.on('hidden', resize);
        resize();
        return map;
    }

    $(function() {
        if (context !== '') {
            var map = load(context, ICON_PATH);
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
