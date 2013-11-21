var utils = {
    getDisplay: function (question, MAXLEN) {
        return utils.getLabel(question, MAXLEN) + " (" + question.value + ")";
    },
    getLabel: function (question, MAXLEN) {
        return utils.truncateLabel((question.repeat ? '- ' : '') + question.label, question.tag == 'hidden' ? ' (Hidden)' : '', MAXLEN);
    },
    truncateLabel: function (label, suffix, MAXLEN) {
        suffix = suffix || "";
        var MAXLEN = MAXLEN || 40,
            maxlen = MAXLEN - suffix.length;
        return ((label.length <= maxlen) ? (label) : (label.slice(0, maxlen) + "...")) + suffix;
    }
};

ko.bindingHandlers.questionsSelect = {
    init: function (element, valueAccessor) {
        $(element).after('<div class="alert alert-error"></div>');
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
            $warning.show().text('We cannot find this question in the form. It is likely that you deleted or renamed the question. Please choose a valid question from the dropdown.');
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
                    return utils.getDisplay(o.question);
                },
                formatResult: function (o) {
                    return utils.getDisplay(o.question, 90);
                },
                dropdownCssClass: 'bigdrop'
            });
        });
        allBindings.optstrText = utils.getLabel;
    }
};