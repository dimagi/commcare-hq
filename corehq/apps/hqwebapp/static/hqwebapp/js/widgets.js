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

        // .hqwebapp-select2 is a basic select2-based dropdown or multiselect
        _.each($(".hqwebapp-select2"), function (element) {
            $(element).select2(additionalConfig);
        });

        // .hqwebapp-autocomplete also allows for free text entry
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
                createTag: function (params) {
                    // Support pasting in comma-separated values
                    var terms = parseEmails(params.term);
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
    };

    var parseEmails = function (input) {
        return $.trim(input).split(/[, ]\s*/);
    };

    return {
        init: init,
        parseEmails: parseEmails,
    };
});
