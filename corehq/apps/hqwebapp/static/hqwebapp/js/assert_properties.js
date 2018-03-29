hqDefine("hqwebapp/js/assert_properties", ['underscore'], function(_) {
    var assert = function(object, required, optional) {
        var all = _.keys(object),
            missing = _.difference(required, all),
            excess = _.difference(all, required, optional);

        if (missing.length) {
            throw new Error("Required properties missing: " + missing.join(", "));
        }

        if (excess.length) {
            throw new Error("Unexpected properties encountered: " + excess.join(", "));
        }

        return true;
    };

    return {
        assert: assert,
    };
});
