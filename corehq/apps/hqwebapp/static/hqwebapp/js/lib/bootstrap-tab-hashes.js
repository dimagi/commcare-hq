// Modified https://gist.github.com/josheinstein/5586469
$(function () {
    if (location.hash.substr(0,2) == "#!") {
        var hash = location.hash.substr(2);
        hash = hash.split('?')[0];
        $("a[href='#" + hash + "']").tab("show");
    }

    $("a[data-toggle='tab']").on("shown", function (e) {
        var hash = $(e.target).attr("href");
        if (hash.substr(0,1) == "#") {
            location.replace("#!" + hash.substr(1));
        }
    });
});
