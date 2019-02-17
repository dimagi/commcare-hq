hqDefine("hqwebapp/js/select2_knockout_bindings_v3.ko", [
    'jquery',
    'knockout',
    'DOMPurify/dist/purify.min',
], function (
    $,
    ko,
    DOMPurify
) {
    /**
     * Converts the bound element to a select2 widget. The value of the binding is
     * a list of strings, or a list of objects with the keys 'id' and 'text' used
     * for the select2's options.
     */
    ko.bindingHandlers.select2 = function () {
        var self = {};

        self.SOURCE_KEY = "select2-source";

        self.updateSelect2Source = function (element, valueAccessor) {
            var source = $(element).data(self.SOURCE_KEY);
            // We clear the array and repopulate it, instead of simply replacing
            // it, because the select2 options are tied to this specific instance.
            while (source.length > 0) {
                source.pop();
            }
            var newItems = ko.utils.unwrapObservable(valueAccessor()) || [];
            for (var i = 0; i < newItems.length; i++) {
                var text = newItems[i].text || newItems[i];
                var id = newItems[i].id || newItems[i];
                source.push({
                    id: id,
                    text: text,
                });
            }
            return source;
        };

        self.init = function (element) {
            var $el = $(element);

            // The select2 jquery element uses the array stored at
            // $el.data(self.SOURCE_KEY) as its data source. Therefore, the options
            // can only be changed by modifying this object, overwriting it will
            // not change the select options.
            $el.data(self.SOURCE_KEY, []);

            $el.select2({
                multiple: false,
                width: "element",
                data: $el.data(self.SOURCE_KEY),
            });
        };

        self.update = function (element, valueAccessor, allBindings) {
            self.updateSelect2Source(element, valueAccessor);

            // Update the selected item
            $(element).val(ko.unwrap(allBindings().value)).trigger("change");
        };

        return self;
    }();

    /**
     * Autocomplete widget based on a select2. Allows free text entry.
     */
    ko.bindingHandlers.autocompleteSelect2 = function () {
        var self = {};

        self.SOURCE_KEY = "select2-source";

        self.select2Options = function (element) {
            var $el = $(element);
            $el.data(self.SOURCE_KEY, []);
            return {
                multiple: false,
                width: "off",
                data: $el.data(self.SOURCE_KEY),
                escapeMarkup: function (text) {
                    return DOMPurify.sanitize(text);
                },
                createSearchChoice: function (term, data) {
                    if (term !== "" && !_.find(data, function (d) { return d.text === term; })) {
                        return {
                            id: term,
                            text: term,
                        };
                    }
                },
            };
        };

        self.init = function (element) {
            self._init(element, self.select2Options(element));
        };

        self._init = function (element, select2Options) {
            $(element).select2(select2Options).on('change', function () {
                $(element).trigger('textchange');
            });
        };

        self.update = function (element, valueAccessor, allBindings) {
            var $el = $(element),
                newValue = ko.unwrap(allBindings().value) || $el.val(),
                source = ko.bindingHandlers.select2.updateSelect2Source(element, valueAccessor);

            // Add free text item to source
            if (newValue && !_.find(source, function (item) { return item.id === newValue; })) {
                source.unshift({
                    id: newValue,
                    text: newValue,
                });
            }

            // Update the selected item
            $el.val(newValue);
            $el.select2("val", newValue);
        };

        return self;
    }();

    return 1;
});
