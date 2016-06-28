// hqDefine intentionally not used

// From http://stackoverflow.com/questions/10523433/how-do-i-keep-the-current-tab-active-with-twitter-bootstrap-after-a-page-reload
$(function() {
    $('a[data-toggle="tab"]').on('shown', function(e){
        //save the latest tab using a cookie:
        $.cookie('last_tab', $(e.target).attr('href'));
    });
    //activate latest tab, if it exists:
    var lastTab = $.cookie('last_tab');
    if (lastTab) {
        $('a[href=' + lastTab + ']').tab('show');
    }
    else
    {
        // Set the first tab if cookie do not exist
        $('a[data-toggle="tab"]:first').tab('show');
    }
});
