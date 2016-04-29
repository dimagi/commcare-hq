function Util() {
}

Util.getQueryParams = function (qs) {
    qs = qs.split("+").join(" ");

    var params = [], tokens,
        re = /[?&]?([^=]+)=([^&]*)/g;

    while (tokens = re.exec(qs)) {
        params.push({k: decodeURIComponent(tokens[1]), v: decodeURIComponent(tokens[2])});
    }

    return params;
}

Util.getSteps = function (qs) {
    urlParams = Util.getQueryParams(qs);
    steps = [];
    for (var i = 0; i < urlParams.length; i++) {
        steps.push(urlParams[i].v)
    }
    return steps;
};