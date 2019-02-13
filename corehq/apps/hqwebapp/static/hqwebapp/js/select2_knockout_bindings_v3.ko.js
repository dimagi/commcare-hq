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
        var that = this;

        this.SOURCE_KEY = "select2-source";

        this.updateSelect2Source = function (element, valueAccessor) {
            var source = $(element).data(that.SOURCE_KEY);
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

        this.init = function (element) {
            var $el = $(element);

            // The select2 jquery element uses the array stored at
            // $el.data(that.SOURCE_KEY) as its data source. Therefore, the options
            // can only be changed by modifying this object, overwriting it will
            // not change the select options.
            $el.data(that.SOURCE_KEY, []);

            $el.select2({
                multiple: false,
                width: "element",
                data: $el.data(that.SOURCE_KEY),
            });
        };

        this.update = function (element, valueAccessor, allBindings) {
            that.updateSelect2Source(element, valueAccessor);

            // Update the selected item
            $(element).val(ko.unwrap(allBindings().value)).trigger("change");
        };
    }();

    /**
     * Autocomplete widget based on a select2. Allows free text entry.
     */
    ko.bindingHandlers.autocompleteSelect2 = function () {
        var that = this;

        this.SOURCE_KEY = "select2-source";

        this.select2Options = function (element) {
            var $el = $(element);
            $el.data(that.SOURCE_KEY, []);
            return {
                multiple: false,
                width: "off",
                data: $el.data(that.SOURCE_KEY),
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

        this.init = function (element) {
            that._init(element, that.select2Options(element));
        };

        this._init = function (element, select2Options) {
            $(element).select2(select2Options).on('change', function () {
                $(element).trigger('textchange');
            });
        };

        this.update = function (element, valueAccessor, allBindings) {
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
    }();

    return 1;
});
