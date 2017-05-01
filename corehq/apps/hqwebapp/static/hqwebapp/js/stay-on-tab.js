// hqDefine intentionally not used

// Modified from
// http://stackoverflow.com/questions/10523433/how-do-i-keep-the-current-tab-active-with-twitter-bootstrap-after-a-page-reload
$(function() {
    // Save latest tab when switching tabs
    $(document).on('shown.bs.tab', 'a[data-toggle="tab"]', function(e){
        var href = $(e.target).attr('href');
        if (href.startsWith("#")) {
            // App manager does complex things with tabs.
            // Ignore those, only deal with simple tabs.
            $.cookie('last_tab', href);
        }
    });

    // Activate latest (or first) tab on document ready
    var lastTab = $.cookie('last_tab');
    if (lastTab) {
        $('a[href="' + lastTab + '"]').tab('show');
    } else {
        $('a[data-toggle="tab"]:first').tab('show');
    }
});
