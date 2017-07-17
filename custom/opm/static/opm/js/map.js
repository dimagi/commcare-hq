/* globals ICON_PATH, load */
ICON_PATH = hqImport("hqwebapp/js/initial_page_data.js").get('icon_path');
hqDefine("opm/js/map.js", function() {
    var context = hqImport("hqwebapp/js/initial_page_data.js").get('context');

    $(function() {
        if (context !== '') {
            load(context, ICON_PATH);
            var div = '<div id="extra-legend" class="control-pane leaflet-control"><h4>AWC Name</h4><div>' +
                    '<table class="enumlegend"><tbody>';
            for(var awc_name in context.config.metrics[0].children[3].color.categories) {
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
