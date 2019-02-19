hqDefine("hqwebapp/js/assert_properties", ['underscore'], function (_) {
    var assertRequired = function (object, required) {
        var all = _.keys(object),
            missing = _.difference(required, all);

        if (missing.length) {
            throw new Error("Required properties missing: " + missing.join(", "));
        }

        return true;
    };

    var assert = function (object, required, optional) {
        assertRequired(object, required);

        var all = _.keys(object),
            excess = _.difference(all, required, optional);
        if (excess.length) {
            throw new Error("Unexpected properties encountered: " + excess.join(", "));
        }

        return true;
    };

    return {
        assert: assert,
        assertRequired: assertRequired,
    };
});
