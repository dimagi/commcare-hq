hqDefine("ewsghana/js/map.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    CONTEXT = initial_page_data('context');
    ICON_PATH = initial_page_data('icon_path');
    MIN_HEIGHT = 300; //px

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
        if (CONTEXT !== '') {
            var map = load(CONTEXT, ICON_PATH);
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
