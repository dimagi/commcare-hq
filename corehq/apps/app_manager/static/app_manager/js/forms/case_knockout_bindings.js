(function () {
    var utils = {
        getIcon: function(question) {
            if (question.tag === 'upload') {
                return '<i class="fa fa-paperclip"></i> ';
            }
            return '';
        },
        getDisplay: function (question, MAXLEN) {
            return utils.getIcon(question) + utils.getLabel(question, MAXLEN)
                    + " (" + (question.hashtagValue || question.value) + ")";
        },
        getTruncatedDisplay: function (question, MAXLEN) {
            return utils.getIcon(question) + utils.getLabel(question, MAXLEN)
                    + " (" + utils.truncateValue(question.hashtagValue || question.value, MAXLEN) + ")";
        },
        getLabel: function (question, MAXLEN) {
            return utils.truncateLabel((question.repeat ? '- ' : '')
                    + question.label, question.tag === 'hidden' ? ' (Hidden)' : '', MAXLEN);
        },
        truncateLabel: function (label, suffix, MAXLEN) {
            suffix = suffix || "";
            var MAXLEN = MAXLEN || 40,
                maxlen = MAXLEN - suffix.length;
            return ((label.length <= maxlen) ? (label) : (label.slice(0, maxlen) + "...")) + suffix;
        },
        truncateValue: function (value, MAXLEN) {
            MAXLEN = MAXLEN || 40;
            return (value.length <= MAXLEN) ? (value) : (value.slice(0, MAXLEN/2) + "..." + value.slice(value.length - MAXLEN/2));
        },
    };

    ko.bindingHandlers.questionsSelect = {
        /*
            The value used with this binding should be in the form:
            [
                {value: "someValue", label: "someLabel"},
                ...
            ]
         */
        init: function (element, valueAccessor) {
            $(element).after('<div class="alert alert-danger"></div>');
        },
        update: function (element, valueAccessor, allBindingsAccessor) {
            var optionObjects = ko.utils.unwrapObservable(valueAccessor());
            var allBindings = ko.utils.unwrapObservable(allBindingsAccessor());
            var value = ko.utils.unwrapObservable(allBindings.value);
            var $warning = $(element).next();
            if (value && !_.some(optionObjects, function (option) {
                return option.value === value;
            })) {
                var option = {
                    label: 'Unidentified Question (' + value + ')',
                    value: value
                };
                optionObjects = [option].concat(optionObjects);
                $warning.show().text('We cannot find this question in the allowed questions for this field. ' +
                    'It is likely that you deleted or renamed the question. ' +
                    'Please choose a valid question from the dropdown.');
            } else {
                $warning.hide();
            }
            _.delay(function () {
                $(element).select2({
                    placeholder: 'Select a Question',
                    data: {
                        results: _(optionObjects).map(function (o) {
                            return {id: o.value, text: utils.getDisplay(o), question: o};
                        })
                    },
                    formatSelection: function (o) {
                        return utils.getTruncatedDisplay(o.question);
                    },
                    formatResult: function (o) {
                        return utils.getTruncatedDisplay(o.question, 90);
                    },
                    dropdownCssClass: 'bigdrop'
                });
            });
            allBindings.optstrText = utils.getLabel;
        }
    };
}());

ko.bindingHandlers.casePropertyAutocomplete = {
    /*
     * Strip "attachment:" prefix and show icon for attachment properties.
     * Replace any spaces in free text with underscores.
     */
    init: function (element, valueAccessor) {
        $(element).on('textchange', function() {
            var $el = $(this);
            if ($el.val().match(/\s/)) {
                var pos = $el.caret('pos');
                $el.val($el.val().replace(/\s/g, '_'));
                $el.caret('pos', pos);
            }
        });
        ko.bindingHandlers.autocompleteAtwho.init(element, valueAccessor);
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
        function wrappedValueAccessor() {
            return _.map(ko.unwrap(valueAccessor()), function(value) {
                if (value.indexOf("attachment:") === 0) {
                    var text = value.substring(11),
                        html = '<i class="fa fa-paperclip"></i> ' + text;
                    return {name: text, content: html};
                }
                return {name: value, content: value};
            })
        }
        ko.bindingHandlers.autocompleteAtwho.update(element, wrappedValueAccessor, allBindingsAccessor);
    },
};

// Originally from http://stackoverflow.com/a/17998880
ko.extenders.withPrevious = function (target) {
    // Define new properties for previous value and whether it's changed
    target.previous = ko.observable();

    // Subscribe to observable to update previous, before change.
    target.subscribe(function (v) {
        target.previous(v);
    }, null, 'beforeChange');

    // Return modified observable
    return target;
};

ko.bindingHandlers.numericValue = {
    init : function(element, valueAccessor, allBindingsAccessor) {
        var underlyingObservable = valueAccessor();
        var interceptor = ko.dependentObservable({
            read: underlyingObservable,
            write: function(value) {
                if ($.isNumeric(value)) {
                    underlyingObservable(parseFloat(value));
                } else if (value === '') {
                    underlyingObservable(null);
                }
            }
        });
        ko.bindingHandlers.value.init(element, function() { return interceptor; }, allBindingsAccessor);
    },
    update : ko.bindingHandlers.value.update
};
