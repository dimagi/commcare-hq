/* globals hqImport */
// copied and modified from https://gist.github.com/dsully/1938283
$(function () {

    function loadPage(url) {
        window.location.href = url;
    }

    // Handle tabs, page reloads & browser forward/back history.
    var History = window.History;

    if (!History.enabled) {
        return false;
    }

    var statechange = function () {
        var State = History.getState();
        var hash  = History.getHash();

        // Our default tab.
        if (!State.data || !State.data.tab) {
            if (hash) {
                State.data.tab = hash;
                window.location.hash = '';
            } else {
                State.data.tab = '';
            }
        }

        var link;
        if (State.data.tab) {
            link = $('a[data-toggle="tab"][href$="#' + State.data.tab + '"]');
        } else {
            // if you can't find it by hash, try matching the url
            // this is for first loading a page,
            // where State.data.tab won't be available
            link = $('a[data-toggle="tab"][href^="' + window.location.pathname + '"]');
            if (link.length !== 0) {
                // If multiple links match the current path - likely because this is the inital page load,
                // so the pathname, foo/bar/, will match all links (since they're of the form foo/bar/#baz,
                // foo/bar/#zap, etc.) - look for any link that has been marked as the default landing page.
                // If there's no default set, ultimately we'll fall back to whatever the first link is.
                if (link.length > 1) {
                    var defaultLink = link.filter("[data-default='1']");
                    if (defaultLink.length) {
                        link = defaultLink;
                    }
                }
                link = link.first();
                History.replaceState({
                    tab: link.attr('href').split('#')[1]
                }, null, State.url);
            }
        }
        link.parent().removeClass('active');    // force tab to load
        link.tab('show');
    };
    $(window).on('load', function() {
        statechange();
    });
    if (document.readyState === "complete") {
        statechange();
    }
    History.Adapter.bind(window, 'statechange', statechange);
    History.Adapter.bind(window, 'statechange', function () {
        var State = History.getState();
        if (!State.data || !State.data.tab) {
            // just go to the url specified with a reload
            loadPage(window.location.href);
        }
    });

    $('a[data-toggle="tab"]').on('shown.bs.tab', function (event) {
        // Set the selected tab to be the current state. But don't update the URL.
        var url = event.target.href.split("#")[0];
        var tab = event.target.href.split("#")[1];
        var pageTitle = $(this).attr('data-pagetitle');
        if (pageTitle) {
            document.title = pageTitle;
        }

        var State = History.getState();

        if (url === window.location.href) {
            // for tabs that we don't want to change the url on
            return;
        }

        if ($('#' + tab).length === 0) {
            loadPage(url);
        }

        // Don't set the state if we haven't changed tabs.
        if (State.data.tab != tab) {
            var message = hqImport("style/js/main.js").beforeUnloadCallback();
            var ask = message !== undefined && message !== undefined;
            if (!ask) {
                History.pushState({'tab': tab}, pageTitle, url);
            } else {
                // instead of using tabs, reload page
                // so as to trigger warning
                event.preventDefault();
                loadPage(url);
            }
        }
    });

    // Handle control-click, middle-click, etc. opening in a new window
    $("a[data-toggle='tab']").on("click", function(event) {
        if (event && (event.metaKey || event.ctrlKey || event.which === 2)) {
            window.open($(event.target).attr("href"), '_blank');

            // Prevent the tab from showing in the current window
            $(event.target).one("show.bs.tab", function() {
                return false;
            });
        }
    });
});
