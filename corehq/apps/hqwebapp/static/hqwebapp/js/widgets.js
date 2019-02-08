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
                tags: true,
            }, additionalConfig));
        });

        _.each($(".hqwebapp-autocomplete-email"), function (input) {
            var $input = $(input);
            $input.select2(_.extend({
                multiple: true,
                placeholder: ' ',
                tags: true,
                tokenSeparators: [",", " "],
                createTag: function (params) {
                    // Support pasting in comma-separated values
                    var terms = $.trim(params.term).split(/,\s*/);
                    if (terms.length === 1) {
                        return {
                            id: terms[0],
                            text: terms[0],
                        };
                    }

                    $input.select2('close');
                    var values = $input.val() || [];
                    if (!_.isArray(values)) {
                        values = [values];
                    }
                    _.each(terms, function (term) {
                        if (!_.contains(values, term)) {
                            $input.append(new Option(term, term));
                            values.push(term);
                        }
                    });
                    $input.val(values).trigger("change");

                    return null;
                },
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
