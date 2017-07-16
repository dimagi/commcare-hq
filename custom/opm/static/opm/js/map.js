hqDefine("opm/js/map.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    CONTEXT = initial_page_data('context');
    ICON_PATH = initial_page_data('icon_path');
    MIN_HEIGHT = 300; //px

    $(function() {
        if (CONTEXT !== '') {
            load(CONTEXT, ICON_PATH);
            var div = '<div id="extra-legend" class="control-pane leaflet-control"><h4>AWC Name</h4><div>' +
                    '<table class="enumlegend"><tbody>';
            for(var awc_name in CONTEXT.config.metrics[0].children[3].color.categories) {
                div += "<tr><td>" + awc_name + "</td></tr>"
            }
            div += '</tbody></table></div></div>';
            $('#info').after(div);

            $('.ticklabel').first().css('top', '143px');
            $('.ticklabel').last().css('top', '7px');
            $('#metrics').on('click', '.choice', function() {
                $('.ticklabel').first().css('top', '143px');
                $('.ticklabel').last().css('top', '7px');
            })
        }
    });
});
