hqDefine('analytix/js/utils', [
    'jquery',
    'underscore',
    'analytix/js/initial',
], function (
    $,
    _,
    initialAnalytics
) {
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
            if (element.nodeType) {
                element = $(element);
            }
            element.click(eventHandler);
        }
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
        if (_.isFunction(callback)) {
            oneTimeCallback = _.once(callback);
            setInterval(oneTimeCallback, timeout ? timeout : 2000);
        }
        return oneTimeCallback;
    };

    /**
     * Initialize an API.
     * @param {Deferred} ready The promise to return (see below). Passed as a parameter
     *  so the calling code can attach callbacks to it before calling this function.
     * @param {string} apiId
     * @param {string/array} scriptUrls - Accepts string or array of strings
     * @param {Logger} logger
     * @param {function} initCallback - Logic to run once any scripts are loaded but before
        the promise this function returns is resolved.
     * @returns {Deferred} A promise that will resolve once the API is fully initialized.
     *  This promise will be rejected if the API fails to initialize for any reason, most
     *  likely because analytics is disabled or because a script failed to load.
     */
    var initApi = function (ready, apiId, scriptUrls, logger, initCallback) {
        logger.verbose.log(apiId || "NOT SET", ["DATA", "API ID"]);

        if (_.isString(scriptUrls)) {
            scriptUrls = [scriptUrls];
        }

        if (!initialAnalytics.getFn('global')(('isEnabled'))) {
            logger.debug.log("Failed to initialize because analytics are disabled");
            ready.reject();
            return ready;
        }

        if (!apiId) {
            logger.debug.log("Failed to initialize because apiId was not provided");
            ready.reject();
            return ready;
        }

        $.when.apply($, _.map(scriptUrls, function (url) { return $.getScript(url); }))
            .done(function () {
                if (_.isFunction(initCallback)) {
                    initCallback();
                }
                logger.debug.log('Initialized');
                ready.resolve();
            }).fail(function () {
                logger.debug.log("Failed to Load Script - Check Adblocker");
                ready.reject();
            });

        return ready;
    };

    return {
        trackClickHelper: trackClickHelper,
        createSafeCallback: createSafeCallback,
        getDateHash: getDateHash,
        initApi: initApi,
    };
});
