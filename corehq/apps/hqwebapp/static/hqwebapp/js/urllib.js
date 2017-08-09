var COMMCAREHQ_URLS = {};
hqDefine('hqwebapp/js/urllib.js', function () {
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
    /*var registerUrl = function(name, url) {
        COMMCAREHQ_URLS[name] = url;
    };*/
    var reverse = function (name) {
        var args = arguments;
        var index = 1;
        if (!COMMCAREHQ_URLS[name]) {
            gather();
            if (!COMMCAREHQ_URLS[name]) {
                throw new Error("URL '" + name + "' not found in registry");
            }
        }
        return COMMCAREHQ_URLS[name].replace(/---/g, function () {
            return args[index++];
        });
    };

    var gather = function() {
        $(".commcarehq-urls").each(function() {
            _.each($(this).children(), function(div) {
                var $div = $(div),
                    data = $div.data();
                COMMCAREHQ_URLS[data.name] = data.value;
                $div.remove();
            });
        });
    };

    $(gather);

    return {
        getUrlParameter: getUrlParameter,
        getUrlParameterFromString: getUrlParameterFromString,
        //registerUrl: registerUrl,
        reverse: reverse,
    };
});
