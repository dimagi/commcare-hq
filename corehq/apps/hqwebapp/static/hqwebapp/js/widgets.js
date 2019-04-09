hqDefine("hqwebapp/js/widgets", [
    'jquery',
    'select2/dist/js/select2.full.min',
], function ($) {
    $(function () {
        // .hqwebapp-select2 is a basic select2-based dropdown or multiselect
        _.each($(".hqwebapp-select2"), function (element) {
            $(element).select2({
                width: '100%',
            });
        });

        // .hqwebapp-autocomplete also allows for free text entry
        _.each($(".hqwebapp-autocomplete"), function (input) {
            var $input = $(input);
            $input.select2({
                multiple: true,
                tags: true,
                width: '100%',
            });
        });

        _.each($(".hqwebapp-autocomplete-email"), function (input) {
            var $input = $(input);
            $input.select2({
                multiple: true,
                placeholder: ' ',
                tags: true,
                width: '100%',
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
            });
        });
    });

    var parseEmails = function (input) {
        return $.trim(input).split(/[, ]\s*/);
    };

    return {
        parseEmails: parseEmails,   // export for testing
    };
});
