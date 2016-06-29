function Util() {}

// from http://stackoverflow.com/questions/439463/how-to-get-get-and-post-variables-with-jquery
Util.getQueryParams = function (qs) {
    qs = qs.split("+").join(" ");

    var params = [], tokens,
        re = /[?&]?([^=]+)=([^&]*)/g;

    while (tokens = re.exec(qs)) {
        params.push({k: decodeURIComponent(tokens[1]), v: decodeURIComponent(tokens[2])});
    }

    return params;
};

/** Given a URL, return the parameters (can be 'step' or 'page) in a map:
 * @param queryString - the URL
 * @returns {{steps: [1, 2, 3], page: [int]}}
 */
Util.getSteps = function (queryString) {
    var urlParams = Util.getQueryParams(queryString);
    var paramMap = {};
    var steps = [];
    for (var i = 0; i < urlParams.length; i++) {
        if (urlParams[i].k.indexOf('step') > -1) {
            steps.push(urlParams[i].v);
        } else if(urlParams[i].k.indexOf('page') > -1) {
            paramMap.page = (urlParams[i].v);
        }
    }
    paramMap.steps = steps;
    return paramMap;
};

Util.setCrossDomainAjaxOptions = function(options) {
    options.type = 'POST';
    options.dataType = "json";
    options.crossDomain = { crossDomain: true};
    options.xhrFields = { withCredentials: true};
    options.contentType = "application/json";
};