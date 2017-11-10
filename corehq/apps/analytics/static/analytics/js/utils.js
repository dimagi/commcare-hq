/* globals _, JSON */
hqDefine('analytics/js/utils', function () {
    'use strict';

    /**
     * A helper function for for tracking google analytics events after a click
     * on an element in the dom.
     *
     * @param {(object|string)} element - A DOM element, jQuery object, or selector.
     * @param {function} trackFunction -
     *      A function that takes a single optional callback.
     *      If called without the callback, this function should
     *      record an event. If called with a callback, this
     *      function should record an event and call the
     *      callback when finished.
     */
    var trackClickHelper = function (element, trackFunction) {
        var eventHandler = function (event) {
            var $this = $(this);
            if (event.metaKey || event.ctrlKey || event.which === 2  // which === 2 for middle click
                || event.currentTarget.target && event.currentTarget !== "_self") {
                // The current page isn't being redirected so just track the click
                // and don't prevent the default click action.
                trackFunction();
            } else {
                // Track how many trackLinkHelper-related handlers
                // this event has, so we only actually click
                // once, after they're all complete.
                var $target = $(event.delegateTarget);
                var count = $target.data("track-link-count") || 0;
                count++;
                $target.data("track-link-count", count);

                event.preventDefault();
                var callbackCalled = false;
                var callback = function () {
                    if (!callbackCalled) {
                        var $target = $(event.delegateTarget);
                        var count = $target.data("track-link-count");
                        count--;
                        $target.data("track-link-count", count);
                        if (!count) {
                            document.location = $this.attr('href');
                        }
                        callbackCalled = true;
                    }
                };
                // callback might not get executed if, say, gtag can't be reached.
                setTimeout(callback, 2000);
                trackFunction(callback);
            }
        };
        if (typeof element === 'string') {
            $(element).on('click', eventHandler);
        } else {
            if (element.nodeType){
                element = $(element);
            }
            element.click(eventHandler);
        }
    };

    /**
     * Inserts a <script async src="srcUrl" type="text/javascript"></script>
     * tag into the DOM.
     * @param {string} srcUrl
     */
    var insertAsyncScript = function (srcUrl) {
        setTimeout(function(){
            var d = document,
                f = d.getElementsByTagName('script')[0],
                s = d.createElement('script');
            s.type = 'text/javascript';
            s.async = true;
            s.src = srcUrl;
            f.parentNode.insertBefore(s, f);
        }, 1);
    };

    /**
     * Makes sure an analytics callback ONCE is called even if the command fails
     * @param {function} callback
     * @param {integer} timeout - (optional)
     * @returns {function} once callback
     */
    var createSafeCallback = function (callback, timeout) {
        var oneTimeCallback = callback;
        if (_.isFunction(callback)){
            oneTimeCallback = _.once(callback);
            setInterval(oneTimeCallback, timeout ? timeout : 2000);
        }
        return oneTimeCallback;
    };

    return {
        trackClickHelper: trackClickHelper,
        insertAsyncScript: insertAsyncScript,
        createSafeCallback: createSafeCallback,
    };
});
