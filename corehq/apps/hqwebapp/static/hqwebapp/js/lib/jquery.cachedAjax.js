/* jQuery cachedAjax plugin v1.0
 * Memoizes Ajax calls.
 *
 * Written by Ricky Mondello
 *   https://github.com/rmondello/cachedAjax
 * Released under the MIT license 
 *   http://www.opensource.org/licenses/mit-license.php
 *
 * This plugin was inspired by John Deerhake's cachedAjax. Unlike John's,
 * this plugin works as a drop-in replacement for $.ajax.
 *   https://github.com/jdeerhake/cachedAjax
 *
 * The key of the cache is the request URL. This assumes that results for
 * requests are stable (i.e. won't change during any given session).
 *
 * $.cachedAjax takes two arguments. The first is a settings object that
 * will be given to $.ajax. For more information about this object, read:
 *   http://api.jquery.com/jQuery.ajax/
 *
 * The second argument is arbitrary data to pass as a second argument into the
 * success callback of the settings object.
 *
 * Like $.ajax, $.cachedAjax returns an XHR object, but only if the request's
 * results weren't cached.
 */

/*global jQuery, window */

jQuery.cachedAjax = (function() {
    var cache = {},
        x = function(conf, callbackData) {
        if (!cache[conf.url]) {
            var succ = conf.success;
            conf.success = function(data) {
                cache[conf.url] = data;
                succ(data, callbackData);
            };
            return jQuery.ajax(conf);
        } else {
            conf.success(cache[conf.url], callbackData);
            return null;
        }
    };

    x.clear = function() {
        cache = {};
    };

    return x;
})();
