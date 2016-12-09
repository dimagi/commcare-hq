var COMMCAREHQ_URLS = {};
hqDefine('hqwebapp/js/urllib.js', function () {
    var getUrlParameter = function getUrlParameter(sParam) {
        var sPageURL = decodeURIComponent(window.location.search.substring(1)),
            sURLVariables = sPageURL.split('&'),
            sParameterName,
            i;

        for (i = 0; i < sURLVariables.length; i++) {
            sParameterName = sURLVariables[i].split('=');

            if (sParameterName[0] === sParam) {
                return sParameterName[1] === undefined ? true : sParameterName[1];
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
        registerUrl: registerUrl,
        reverse: reverse,
    };
});
