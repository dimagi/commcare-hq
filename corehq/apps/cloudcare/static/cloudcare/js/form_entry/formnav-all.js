// preloaders are deprecated -- for backwards compatibility
function init_preloaders(preloaders) {
    if (preloaders == null) {
        return null;
    }

    var preload_data = {};
    for (var type in preloaders) {
        var dict = preloaders[type];

        preload_data[type] = {};
        for (var key in dict) {
            var val = dict[key];

            // this special character indicates a server preloader, which 
            // we make a synchronous request for
            if (val && val.indexOf("<") === 0) {
                valback = jQuery.ajax({
                    url: PRELOADER_URL,
                    type: 'GET',
                    data: {
                        "param": val
                    },
                    async: false
                }).responseText;
                preload_data[type][key] = valback;
            } else {
                preload_data[type][key] = val;
            }
        }
    }
    return preload_data;
}
