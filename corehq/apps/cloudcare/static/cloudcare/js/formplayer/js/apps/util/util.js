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

// Given a URL, return the parameter values (in our case they can only be steps)
Util.getSteps = function (qs) {
    var urlParams = Util.getQueryParams(qs);
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