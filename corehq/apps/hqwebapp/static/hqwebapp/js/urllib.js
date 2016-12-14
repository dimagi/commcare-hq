var COMMCAREHQ_URLS = {};
hqDefine('hqwebapp/js/urllib.js', function () {
    // http://stackoverflow.com/a/21903119/240553
    var getUrlParameter = function (param) {
        return getUrlParameterFromString(param, window.location.search);
    };
    var getUrlParameterFromString = function (param, search) {
        var pageUrl = decodeURIComponent(search.substring(1)),
            urlVariables = pageUrl.split('&'),
            parameterName,
            i;

        for (i = 0; i < urlVariables.length; i++) {
            parameterName = urlVariables[i].split('=');

            if (parameterName[0] === param) {
                return parameterName[1] === undefined ? true : parameterName[1];
            }
        }
    };
    var registerUrl = function(name, url) {
        COMMCAREHQ_URLS[name] = url;
    };
    var reverse = function (name) {
        var args = arguments;
        var index = 1;
        return COMMCAREHQ_URLS[name].replace(/---/g, function () {
            return args[index++];
        });
    };
    return {
        getUrlParameter: getUrlParameter,
        getUrlParameterFromString: getUrlParameterFromString,
        registerUrl: registerUrl,
        reverse: reverse,
    };
});
