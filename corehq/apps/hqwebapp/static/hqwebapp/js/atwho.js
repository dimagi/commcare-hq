hqDefine('hqwebapp/js/atwho', ["underscore"], function (_) {
    var _init = function($input, options, afterInsert, replaceValue) {
        $input.atwho(options).on("inserted.atwho", function(event, $li, otherEvent) {
            if (replaceValue){
                $input.val($input.data("selected-value")).change();
            }

            if (afterInsert) {
                afterInsert();
            }
        });
    };

    /**
     * Apply an atwho-based autocomplete to the given input. Options:
     *  ajax: Overrides for ajax call if data is to be fetched form server.
     *      Suggest at least overriding url and data.
     *  afterInsert: will be called after new value is selected.
     */
    var init = function($input, options) {
        var replaceValue = options.replaceValue === undefined || options.replaceValue;
        var atwhoOptions = {
            at: "",
            limit: Infinity,
            maxLen: Infinity,
            suffix: "",
            tabSelectsMatch: false,
            callbacks: {
                filter: function(query, data, searchKey) {
                    return _.filter(data, function(item) {
                        return item.name.indexOf(query) !== -1;
                    });
                },
                matcher: function(flag, subtext, should_startWithSpace) {
                    return $input.val();
                },
                beforeInsert: function(value, $li) {
                    // This and the inserted.atwho handler below ensure that the entire
                    // input's value is replaced, regardless of where the cursor is
                    if (replaceValue){
                        $input.data("selected-value", value);
                    }
                },
            },
        };
        atwhoOptions = _.defaults(options.atwhoOptions || {}, atwhoOptions);

        if (options.ajax && options.ajax.url) {
            $input.one('focus', function () {
                $.ajax(_.defaults(options.ajax, {
                    success: function (data) {
                        atwhoOptions.data = data;
                        _init($input, atwhoOptions, options.afterInsert, replaceValue);
                        $input.atwho('run');
                    },
                }));
            });
        } else {
            _init($input, atwhoOptions, options.afterInsert, replaceValue);
        }
    };

    return {
        init: init,
    };
});
