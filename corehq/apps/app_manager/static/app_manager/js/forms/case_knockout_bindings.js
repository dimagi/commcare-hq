<<<<<<< HEAD
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import DOMPurify from "dompurify";
import "hqwebapp/js/atwho";  // autocompleteAtwho
import "select2/dist/js/select2.full.min";

var utils = {
=======
import $ from 'jquery';
import ko from 'knockout';
import _ from 'underscore';
import DOMPurify from 'dompurify';
import "jquery-textchange/jquery.textchange";
import 'hqwebapp/js/atwho';    // autocompleteAtwho
import 'select2/dist/js/select2.full.min';

const utils = {
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
    _getIcon: function (question) {
        if (question.tag === 'upload') {
            return '<i class="fa fa-paperclip"></i> ';
        }
        return '';
    },
    getDisplay: function (question, MAXLEN) {
        return utils._getIcon(question) + utils._getLabel(question, MAXLEN)
                + " (" + (question.hashtagValue || question.value) + ")";
    },
    getTruncatedDisplay: function (question, MAXLEN) {
        return utils._getIcon(question) + utils._getLabel(question, MAXLEN)
                + " (" + utils._truncateValue(question.hashtagValue || question.value, MAXLEN) + ")";
    },
    _getLabel: function (question, MAXLEN) {
        return utils._truncateLabel((question.repeat ? '- ' : '')
                + question.label, question.tag === 'hidden' ? ' (Hidden)' : '', MAXLEN);
    },
    _truncateLabel: function (label, suffix, MAXLEN) {
        suffix = suffix || "";
        MAXLEN = MAXLEN || 40;
        const maxlen = MAXLEN - suffix.length;
        return ((label.length <= maxlen) ? (label) : (label.slice(0, maxlen) + "...")) + suffix;
    },
    _truncateValue: function (value, MAXLEN) {
        MAXLEN = MAXLEN || 40;
        return (value.length <= MAXLEN) ? (value) : (value.slice(0, MAXLEN / 2) + "..." + value.slice(value.length - MAXLEN / 2));
    },
};

<<<<<<< HEAD
var questionsById = {};

// Transforms contents of this binding's value into a list of objects to feed to select2
var _valueToSelect2Data = function (optionObjects) {
    var data = _(optionObjects).map(function (o) {
=======
const questionsById = {};

// Transforms contents of this binding's value into a list of objects to feed to select2
const _valueToSelect2Data = function (optionObjects) {
    let data = _(optionObjects).map(function (o) {
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
        o = _.extend(o, {
            id: o.value,
            text: utils.getDisplay(o),
        });
        questionsById[o.id] = o;
        return o;
    });
    data = [{id: '', text: ''}].concat(data);    // prepend option for placeholder
    return data;
};

ko.bindingHandlers.questionsSelect = {
    /*
        The value used with this binding should be in the form:
        [
            {value: "someValue", label: "someLabel"},
            ...
        ]
     */
    init: function (element, valueAccessor, allBindingsAccessor) {
<<<<<<< HEAD
        var optionObjects = ko.utils.unwrapObservable(valueAccessor()),
=======
        let optionObjects = ko.utils.unwrapObservable(valueAccessor()),
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
            allBindings = ko.utils.unwrapObservable(allBindingsAccessor()),
            value = ko.utils.unwrapObservable(allBindings.value);

        // Add a warning if the current value isn't a legitimate question
        if (value && !_.some(optionObjects, function (option) {
            return option.value === value;
        })) {
<<<<<<< HEAD
            var option = {
=======
            const option = {
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
                label: gettext('Unidentified Question') + ' (' + value + ')',
                value: value,
            };
            optionObjects = [option].concat(optionObjects);
<<<<<<< HEAD
            var $warning = $('<div class="help-block"></div>').text(gettext(
=======
            const $warning = $('<div class="help-block"></div>').text(gettext(
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
                'We cannot find this question in the allowed questions for this field. ' +
                'It is likely that you deleted or renamed the question. ' +
                'Please choose a valid question from the dropdown.',
            ));
            $(element).after($warning);
            $(element).parent().addClass('has-error');
        }

        // Initialize select2
        $(element).select2({
            placeholder: gettext('Select a Question'),
            dropdownCssClass: 'bigdrop',
            escapeMarkup: function (m) {
<<<<<<< HEAD
                var paperclip = '<i class="fa fa-paperclip"></i> ';
=======
                let paperclip = '<i class="fa fa-paperclip"></i> ';
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
                if (m.includes(paperclip)) {
                    m = m.replace(paperclip, '');
                } else {
                    paperclip = '';
                }
                return paperclip + DOMPurify.sanitize(m).replace(/</g, '&lt;').replace(/>/g, '&gt;');
            },
            data: _valueToSelect2Data(optionObjects),
            width: '100%',
            templateSelection: function (o) {
                if (!o.id) {
                    // This is the placeholder
                    return o.text;
                }
                return utils.getTruncatedDisplay(questionsById[o.id]);
            },
            templateResult: function (o) {
                if (!o.value) {
                    // This is some select2 system option, like 'Searching...' text
                    return o.text;
                }
                return utils.getTruncatedDisplay(questionsById[o.id], 90);
            },
        });
        $(element).val(value).trigger('change.select2');
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
<<<<<<< HEAD
        var $element = $(element),
=======
        const $element = $(element),
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
            newSelect2Data = _valueToSelect2Data(ko.utils.unwrapObservable(valueAccessor())),
            oldOptionElements = $element.find("option"),
            oldValues = _.map(oldOptionElements, function (o) { return o.value; }),
            newValues = _.pluck(newSelect2Data, 'id');

        // Add any new options
        _.each(newSelect2Data, function (option) {
            if (!_.contains(oldValues, option.id)) {
                $element.append(new Option(option.text, option.id));
            }
        });

        // Remove any options that are no longer relevant
        _.each(oldOptionElements, function (option) {
            if (option.value && !_.contains(newValues, option.value)) {
                $(option).remove();
            }
        });

        // If there was an error but it's fixed now, remove it
<<<<<<< HEAD
        var $container = $element.parent(),
=======
        const $container = $element.parent(),
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
            allBindings = ko.utils.unwrapObservable(allBindingsAccessor()),
            value = ko.utils.unwrapObservable(allBindings.value);
        if ($container.hasClass("has-error") && _.contains(newValues, value)) {
            $container.removeClass("has-error");
            $container.find(".help-block").remove();
        }

        $element.trigger('change.select2');
    },
};

ko.bindingHandlers.casePropertyAutocomplete = {
    /*
     * Strip "attachment:" prefix and show icon for attachment properties.
     * Replace any spaces in free text with underscores.
     */
    init: function (element, valueAccessor) {
        $(element).on('textchange', function () {
<<<<<<< HEAD
            var $el = $(this);
            if ($el.val().match(/\s/)) {
                var pos = $el.caret('pos');
=======
            const $el = $(this);
            if ($el.val().match(/\s/)) {
                const pos = $el.caret('pos');
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
                $el.val($el.val().replace(/\s/g, '_'));
                $el.caret('pos', pos);
            }
        });
        ko.bindingHandlers.autocompleteAtwho.init(element, valueAccessor);
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
        function wrappedValueAccessor() {
            return _.map(ko.unwrap(valueAccessor()), function (value) {
                if (value.indexOf("attachment:") === 0) {
<<<<<<< HEAD
                    var text = value.substring(11),
=======
                    const text = value.substring(11),
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
                        html = '<i class="fa fa-paperclip"></i> ' + text;
                    return {name: text, content: html};
                }
                return {name: value, content: value};
            });
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
    init: function (element, valueAccessor, allBindingsAccessor) {
<<<<<<< HEAD
        var underlyingObservable = valueAccessor();
        var interceptor = ko.dependentObservable({
=======
        const underlyingObservable = valueAccessor();
        const interceptor = ko.dependentObservable({
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
            read: underlyingObservable,
            write: function (value) {
                if ($.isNumeric(value)) {
                    underlyingObservable(parseFloat(value));
                } else if (value === '') {
                    underlyingObservable(null);
                }
            },
        });
        ko.bindingHandlers.value.init(element, function () { return interceptor; }, allBindingsAccessor);
    },
    update: ko.bindingHandlers.value.update,
};
<<<<<<< HEAD
=======

export default ko.bindingHandlers;
>>>>>>> c7c8bb7678ce09f0135156712844e9a4524951b4
