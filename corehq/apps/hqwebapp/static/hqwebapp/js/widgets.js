/**
 * Temporary for select2 migration.
 * This should only be referenced by hqwebapps/js/select2_v3 and hqwebapps/js/select2_v4
 * All client code should depend on one of those two modules.
 */
hqDefine("hqwebapp/js/widgets", [
    'jquery',
], function ($) {
    var init = function (additionalConfig) {
        additionalConfig = additionalConfig || {};
        _.each($(".hqwebapp-autocomplete"), function (input) {
            var $input = $(input);
            $input.select2(_.extend({
                multiple: true,
                tags: $input.data("choices"),
            }, additionalConfig));
        });

        _.each($(".ko-select2"), function (element) {
            $(element).select2(additionalConfig);
        });
    };

    return {
        init: init,
    };
});
