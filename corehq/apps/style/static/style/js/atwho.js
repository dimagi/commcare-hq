hqDefine('style/js/atwho', function () {
    var _init = function($input, options, callback) {
        $input.atwho(options).on("inserted.atwho", function(event, $li, otherEvent) {
            $input.val($input.data("selected-value")).change();

            if (callback) {
                callback();
            }
        });
    };

    /**
     * Apply an atwho-based autocomplete to the given input.
     *  ajaxOptions: Optional overrides for ajax call if data is to be fetched form server.
     *      Suggest at least overriding url and data.
     *  callback: Optional, will be called after new value is selected.
     */
    var init = function($input, ajaxOptions, callback) {
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
                    $input.data("selected-value", value);
                },
            },
        };

        if (ajaxOptions && ajaxOptions.url) {
            $input.one('focus', function () {
                $.ajax(_.defaults(ajaxOptions, {
                    success: function (data) {
                        atwhoOptions.data = data;
                        _init($input, atwhoOptions, callback);
                        $input.atwho('run');
                    },
                }));
            });
        } else {
            _init($input, atwhoOptions, callback);
        }
    };

    return {
        init: init,
    };
});
