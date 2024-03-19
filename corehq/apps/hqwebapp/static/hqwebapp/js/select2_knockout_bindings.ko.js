"use strict";
hqDefine("hqwebapp/js/select2_knockout_bindings.ko", [
    'jquery',
    'underscore',
    'knockout',
    'DOMPurify/dist/purify.min',
    'select2/dist/js/select2.full.min',
], function (
    $,
    _,
    ko,
    DOMPurify
) {
    /**
     * Converts the bound element to a select2 widget, using the element's existing
     * options as data. This does not allow the options to change dynamically.
     * The binding's value is ignored. This is useful for select2s that are part of
     * a knockout-controlled UI but don't need dynamic options.
     */
    ko.bindingHandlers.staticSelect2 = function () {
        var self = {};

        self.init = function (element) {
            $(element).select2({
                width: "element",
            });
        };

        self.update = function () {
            // Do nothing, this should never get called
        };

        return self;
    }();

    /**
     * Converts the bound element to a select2 widget. The value of the binding is
     * a list of strings, or a list of objects with the keys 'id' and 'text' used
     * for the select2's options.
     */
    ko.bindingHandlers.select2 = function () {
        var self = {};

        self.updateSelect2Source = function (element, valueAccessor) {
            var $el = $(element);
            $el.empty();
            var newItems = ko.utils.unwrapObservable(valueAccessor()) || [];
            for (var i = 0; i < newItems.length; i++) {
                var text = newItems[i].text || newItems[i];
                var id = newItems[i].id || newItems[i];
                $el.append(new Option(text, id));
            }
        };

        self.init = function (element) {
            var $el = $(element);
            $el.select2({
                width: "element",
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

        self.select2Options = function (element) {
            var $el = $(element);
            return {
                placeholder: $el.attr("placeholder") || ' ',
                multiple: false,
                width: "100%",
                escapeMarkup: function (text) {
                    return DOMPurify.sanitize(text);
                },
                tags: true,
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
                newValue = ko.unwrap(allBindings().value);

            ko.bindingHandlers.select2.updateSelect2Source(element, valueAccessor);

            // Add free text item to source
            if (newValue && !_.find($el.find("option"), function (option) { return option.value === newValue; })) {
                $el.prepend(new Option(newValue, newValue));
            }

            // Update the selected item
            $el.val(newValue);
            _.delay(function () {
                $el.trigger("change.select2");  // get select2 to display value
            });
        };

        return self;
    }();

    return 1;
});
