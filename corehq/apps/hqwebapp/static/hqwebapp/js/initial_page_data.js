/*
 *  Manage data needed by JavaScript but supplied by server,
 *  with special handling for urls.
 *
 *  In django templates, use {% initial_page_data varName varValue %} to
 *  define data, then in JavaScript use this module's get function to
 *  access it.
 */
hqDefine('hqwebapp/js/initial_page_data', function () {
    var data_selector = ".initial-page-data",
        data = {},
        url_selector = ".commcarehq-urls",
        urls = {};

    /*
     *  Find any unregistered data. Error on any duplicates.
     */
    var gather = function(selector, existing) {
        existing = existing || {};
        $(selector).each(function() {
            _.each($(this).children(), function(div) {
                var $div = $(div),
                    data = $div.data();
                if (existing[data.name] !== undefined) {
                    throw new Error("Duplicate key in initial page data: " + data.name);
                }
                existing[data.name] = data.value;
                $div.remove();
            });
        });
        return existing;
    };

    /*
     * Fetch a named value.
     */
    var get = function(name) {
        if (data[name] === undefined) {
            data = gather(data_selector, data);
        }
        return data[name];
    };

    // http://stackoverflow.com/a/21903119/240553
    var getUrlParameter = function (param) {
        return getUrlParameterFromString(param, window.location.search);
    };

    var getUrlParameterFromString = function (param, search) {
        var pageUrl = search.substring(1),
            urlVariables = pageUrl.split('&');

        for (var i = 0; i < urlVariables.length; i++) {
            var keyValue = urlVariables[i].split('=');
            var key = decodeURIComponent(keyValue[0]);
            var value = decodeURIComponent(keyValue[1]);

            if (key === param) {
                return value === undefined ? true : value;
            }
        }
    };

    /*
     *  Manually add url to registry.
     */
    var registerUrl = function(name, url) {
        urls[name] = url;
    };

    /*
     *  Fetch actual url, based on name.
     */
    var reverse = function (name) {
        var args = arguments;
        var index = 1;
        if (!urls[name]) {
            urls = gather(url_selector, urls);
            if (!urls[name]) {
                throw new Error("URL '" + name + "' not found in registry");
            }
        }
        return urls[name].replace(/---/g, function () {
            return args[index++];
        });
    };

    $(function() {
        data = gather(data_selector, data);
        urls = gather(url_selector, urls);
    });

    return {
        gather: gather,
        get: get,
        getUrlParameter: getUrlParameter,
        getUrlParameterFromString: getUrlParameterFromString,
        registerUrl: registerUrl,
        reverse: reverse,
    };
});
