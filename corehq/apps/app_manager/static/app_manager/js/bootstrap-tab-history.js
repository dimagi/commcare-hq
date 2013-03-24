// copied from https://gist.github.com/dsully/1938283
$(document).ready(function() {

    // Handle tabs, page reloads & browser forward/back history.
    var History = window.History;

    if (!History.enabled) {
        return false;
    }

    $(window).bind('load statechange', function () {
        var State = History.getState();
        var hash  = History.getHash();

        // Our default tab.
        if (!State.data || !State.data.tab) {
            if (hash) {
                State.data.tab = hash;
                window.location.hash = '';
            } else {
                State.data.tab = 'DEFAULT ACTIVE TAB';
            }
        }

        $('ul.nav-tabs > li > a[href="#' + State.data.tab + '"]').tab('show');
    });

    $('a[data-toggle="tab"]').on('shown', function (event) {

        // Set the selected tab to be the current state. But don't update the URL.
        var url = event.target.href.split("#")[0];
        var tab = event.target.href.split("#")[1];

        var State = History.getState();

        // Don't set the state if we haven't changed tabs.
        if (State.data.tab != tab) {
            History.pushState({'tab': tab}, null, url);
        }
    });
});