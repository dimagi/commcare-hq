hqDefine('hqwebapp/js/urllib.js', function () {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js"),
        urls = {};

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
    var reverse = function (name) {
        var args = arguments;
        var index = 1;
        if (!urls[name]) {
            urls = initial_page_data.gather(".commcarehq-urls", urls);
            if (!urls[name]) {
                throw new Error("URL '" + name + "' not found in registry");
            }
        }
        return urls[name].replace(/---/g, function () {
            return args[index++];
        });
    };

    $(function() {
        urls = initial_page_data.gather(".commcarehq-urls", urls);
    });

    return {
        getUrlParameter: getUrlParameter,
        getUrlParameterFromString: getUrlParameterFromString,
        reverse: reverse,
    };
});
