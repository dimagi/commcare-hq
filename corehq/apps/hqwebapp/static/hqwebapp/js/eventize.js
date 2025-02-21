hqDefine('hqwebapp/js/eventize', [], function () {
    return function (that) {
        var events = {};
        that.on = function (tag, callback) {
            if (events[tag] === undefined) {
                events[tag] = [];
            }
            events[tag].push(callback);
            return that;
        };
        that.fire = function (tag, e) {
            var i;
            if (events[tag] !== undefined) {
                for (i = 0; i < events[tag].length; i += 1) {
                    events[tag][i].apply(that, [e]);
                }
            }
            return that;
        };
        return that;
    };
});
