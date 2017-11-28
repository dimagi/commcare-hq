/* globals _, JSON */
hqDefine('analytix/js/utils', function () {
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
     * Inserts a <script src="srcUrl" type="text/javascript"></script>
     * tag into the DOM.
     * @param {string} scriptSrc
     * @param {function} loggingFn - logs on success or failure of script
     * @param {object} options - (optional) options added on to the script
     */
    var insertScript = function (scriptSrc, loggingFn, options) {
        setTimeout(function(){
            var doc = document,
                firstScriptTag = doc.getElementsByTagName('script')[0],
                script = doc.createElement('script');
            script.type = 'text/javascript';
            script.async = true;
            script.src = scriptSrc;
            _.each(options || {}, function(val, key) {
                script[key] = val;
            });
            script.addEventListener('error', function () {
                loggingFn(scriptSrc, "Failed to Load Script - Check Adblocker");
            });
            script.addEventListener('load', function () {
                loggingFn(scriptSrc, "Loaded Script");
            });
            firstScriptTag.parentNode.insertBefore(script, firstScriptTag);
        }, 1);
    };

    var getDateHash = function () {
        var e = 3e5;
        return Math.ceil(new Date() / e) * e;
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
        insertScript: insertScript,
        createSafeCallback: createSafeCallback,
        getDateHash: getDateHash,
    };
});
