/* globals hqDefine */
hqDefine('appstore/js/appstore_base.js', function () {
    // This assures that all the result elements are the same height
    function assure_correct_spacing() {
        $('.results').each(function(){
            var highest = 0;
            var $wells = $(this).find('.well');
            $wells.each(function(){
                var height = $(this).children(":first").height();
                highest = (height > highest) ? height : highest;
            });
            $wells.height(highest);
        });
    }
    $(window).on('load', assure_correct_spacing);
    if (document.readyState === "complete") {
        assure_correct_spacing();
    }
    $(window).resize(assure_correct_spacing);

    $(function(){
        var app_ids = hqImport('hqwebapp/js/initial_page_data.js').get('app_ids');
        _.each(app_ids, function(id) {
            gaTrackLink($('#view_button_' + id), 'Exchange', 'View button', id);
        });
    });
});
