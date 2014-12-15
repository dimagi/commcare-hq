var generateEditableHandler = function (spec) {
    return {
        init: function (element, valueAccessor, allBindingsAccessor, viewModel) {
            var input = spec.getEdit().appendTo(element);
            var span = spec.getNonEdit().appendTo(element);
            var editing = allBindingsAccessor().editing;
            var inputHandlers = allBindingsAccessor().inputHandlers;
            spec.editHandler.init(input.get(0), valueAccessor, allBindingsAccessor, viewModel);
            (spec.nonEditHandler.init || function () {})(span.get(0), valueAccessor, allBindingsAccessor, viewModel);
            for (var name in inputHandlers) {
                if (inputHandlers.hasOwnProperty(name)) {
                    ko.bindingHandlers[name].init(input.get(0), (function (name) {
                        return function () {
                            return inputHandlers[name];
                        };
                    }(name)), allBindingsAccessor, viewModel);
                }
            }

            if (editing) {
                editing.subscribe(function () {
                    ko.bindingHandlers.editableString.update(element, valueAccessor, allBindingsAccessor, viewModel);
                });
            }
        },
        update: function (element, valueAccessor, allBindingsAccessor, viewModel) {
            var input = spec.getEdit(element);
            var span = spec.getNonEdit(element);
            var editing = allBindingsAccessor().editing || function () { return true; };
            var inputHandlers = allBindingsAccessor().inputHandlers;

            spec.editHandler.update(input.get(0), valueAccessor, allBindingsAccessor, viewModel);
            spec.nonEditHandler.update(span.get(0), valueAccessor, allBindingsAccessor, viewModel);

            for (var name in inputHandlers) {
                if (inputHandlers.hasOwnProperty(name)) {
                    ko.bindingHandlers[name].update(input.get(0), (function (name) {
                        return function () {
                            return inputHandlers[name];
                        };
                    }(name)), allBindingsAccessor, viewModel);
                }
            }

            if (editing()) {
                input.show();
                span.hide();
            } else {
                input.hide();
                span.show();
            }
        }
    };
};

ko.bindingHandlers.staticChecked = {
    init: function (element) {
        $('<span class="icon"></span>').appendTo(element);
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
        var value = ko.utils.unwrapObservable(valueAccessor());
        var span = $('span', element);
        var allBindings = allBindingsAccessor();
        var iconTrue = ko.utils.unwrapObservable(allBindings.iconTrue) || 'icon-ok',
            iconFalse = ko.utils.unwrapObservable(allBindings.iconFalse) || '';

        if (value) {
            span.removeClass(iconFalse).addClass(iconTrue);
        } else {
            span.removeClass(iconTrue).addClass(iconFalse);
        }
    }
};

ko.bindingHandlers.editableString = generateEditableHandler({
    editHandler: ko.bindingHandlers.value,
    nonEditHandler: ko.bindingHandlers.text,
    getEdit: function (element) {
        if (element) {
            return $('input', element);
        } else {
            return $('<input type="text"/>');
        }
    },
    getNonEdit: function (element) {
        if (element) {
            return $('span', element);
        } else {
            return $('<span/>');
        }
    }
});

ko.bindingHandlers.editableBool = generateEditableHandler({
    editHandler: ko.bindingHandlers.checked,
    nonEditHandler: ko.bindingHandlers.staticChecked,
    getEdit: function (element) {
        if (element) {
            return $('input', element);
        } else {
            return $('<input type="checkbox"/>');
        }
    },
    getNonEdit: function (element) {
        if (element) {
            return $('span', element);
        } else {
            return $('<span/>');
        }
    }
});

ko.bindingHandlers.langcode = {
    init: function (element, valueAccessor, allBindingsAccessor) {
        ko.bindingHandlers.editableString.init(element, valueAccessor, function () {
            var b = allBindingsAccessor();
            b.valueUpdate = b.valueUpdate || [];
            if (typeof b.valueUpdate === 'string') {
                b.valueUpdate = [b.valueUpdate];
            }
            b.valueUpdate.push('autocompletechange');
            return b;
        });
        $('input', element).addClass('short code').langcodes();
    },
    update: ko.bindingHandlers.editableString.update
};
ko.bindingHandlers.sortable = {
    updateSortableList: function (itemList) {
        _(itemList()).each(function (item, index) {
            if (item._sortableOrder === undefined) {
                item._sortableOrder = ko.observable(index);
            } else {
                item._sortableOrder(index);
            }
        });
    },
    getList: function (valueAccessor) {
        /* this function's logic follows that of ko.bindingHandlers.foreach.makeTemplateValueAccessor */
        var modelValue = valueAccessor(),
            unwrappedValue = ko.utils.peekObservable(modelValue);
            if ((!unwrappedValue) || typeof unwrappedValue.length == "number") {
                return modelValue;
            } else {
                return unwrappedValue['data'];
            }
    },
    init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        // based on http://www.knockmeout.net/2011/05/dragging-dropping-and-sorting-with.html
        // note: although by this point we've deviated from that solution quite a bit
        var list = ko.bindingHandlers.sortable.getList(valueAccessor);
        var forceUpdate = function () {
            ko.bindingHandlers.sortable.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        };
        list.subscribe(forceUpdate);
        $(element).sortable({
            handle: '.sortable-handle',
            update: function(event, ui) {
                var parent = ui.item.parent(),
                    oldPosition = ui.item.data('order');
                if (oldPosition === undefined) {
                    console.warn(
                        "NOT UPDATING THE SORT OF THE ACTUAL LIST! " +
                        "Did you forget to add `attr: {'data-order': _sortableOrder}` " +
                        "to the data-bind attribute of your main sorting " +
                        "element?"
                    );
                    return;
                }
                oldPosition = parseInt(oldPosition);
                var newPosition = ko.utils.arrayIndexOf(parent.children(), ui.item.get(0)),
                    item = list()[oldPosition];

                if (item === undefined) {
                    forceUpdate();
                    console.warn('Fetched an undefined item. Check your code.');
                    return;
                }

                if (item !== undefined) {
                    // this is voodoo to me, but I have to remove the ui item from its new position
                    // and *not replace* it in its original position for all the foreach mechanisms to work correctly
                    // I found this by trial and error
                    ui.item.detach();
                    //remove the item and add it back in the right spot
                    if (newPosition >= 0) {
                        list.remove(item);
                        list.splice(newPosition, 0, item);
                        // Knockout 2.3 fix: refresh all of the `data-order`s
                        // this is an O(n) operation, so if experiencing slowness
                        // start here
                        parent.children().each(function (i) {
                            $(this).data('order', i);
                        });
                    }
                }
            }
        });
        return ko.bindingHandlers.foreach.init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
    },
    update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var list = ko.bindingHandlers.sortable.getList(valueAccessor);
        ko.bindingHandlers.sortable.updateSortableList(list);
        return ko.bindingHandlers.foreach.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
    }
};

ko.bindingHandlers.saveButton = {
    init: function (element, getSaveButton) {
        getSaveButton().ui.appendTo(element);
    }
};

ko.bindingHandlers.saveButton2 = {
    init: function (element, valueAccessor, allBindingsAccessor) {
        var saveOptions = allBindingsAccessor().saveOptions,
            state = valueAccessor(),
            saveButton = SaveButton.init({
                save: function () {
                    saveButton.ajax(saveOptions());
                }
            });
        saveButton.ui.appendTo(element);
        element.saveButton = saveButton;
        saveButton.on('state:change', function () {
            state(saveButton.state);
        });
    },
    update: function (element, valueAccessor) {
        var state = ko.utils.unwrapObservable(valueAccessor());
        element.saveButton.setStateWhenReady(state);
    }
};

ko.bindingHandlers.deleteButton = {
    init: function (element, valueAccessor, allBindingsAccessor) {
        var saveOptions = allBindingsAccessor().saveOptions,
            state = valueAccessor(),
            deleteButton = DeleteButton.init({
                save: function () {
                    deleteButton.ajax(saveOptions());
                }
            });
        deleteButton.ui.appendTo(element);
        element.deleteButton = deleteButton;
        deleteButton.on('state:change', function () {
            state(deleteButton.state);
        });
    },
    update: function (element, valueAccessor) {
        var state = ko.utils.unwrapObservable(valueAccessor());
        element.deleteButton.setStateWhenReady(state);
    }
};

ko.bindingHandlers.modal = {
    init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        $(element).addClass('modal fade').modal({
            show: false,
            backdrop: false
        });
//        ko.bindingHandlers['if'].init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
    },
    update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        ko.bindingHandlers.visible.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        var value = ko.utils.unwrapObservable(valueAccessor());
//        ko.bindingHandlers['if'].update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        if (value) {
            $(element).modal('show');
        } else {
            $(element).modal('hide');
        }
    }
};

ko.bindingHandlers.openModal = {
    init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var templateID = valueAccessor(),
            modal = $('<div></div>').addClass('modal fade').appendTo('body'),
            newValueAccessor = function () {
                var clickAction = function () {
                    ko.bindingHandlers.template.init(modal.get(0), function () {
                        return templateID;
                    }, allBindingsAccessor, viewModel, bindingContext);
                    ko.bindingHandlers.template.update(modal.get(0), function () {
                        return templateID;
                    }, allBindingsAccessor, viewModel, bindingContext);
                    modal.modal('show');
                };
                return clickAction;
            };
        ko.bindingHandlers.click.init(element, newValueAccessor, allBindingsAccessor, viewModel, bindingContext);
    }
};

ko.bindingHandlers.openJqm = {
    init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var modal = $('<div></div>').addClass('jqmWindow').appendTo('body'),
            newValueAccessor = function () {
                var clickAction = function () {
                    modal.jqm({ajax: $(element).data('ajaxSource')}).jqmShow();
                };
                return clickAction;
            };
        ko.bindingHandlers.click.init(element, newValueAccessor, allBindingsAccessor, viewModel, bindingContext);
//            $('#odk-install-placeholder').jqm({ajax: '@href', trigger: 'a.odk_install',
//            ajaxText: "Please wait while we load that for you..." });
    },
    update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        $(element).data('ajaxSource', ko.utils.unwrapObservable(valueAccessor()));
    }
};

ko.bindingHandlers.visibleFade = {
    'update': function (element, valueAccessor) {
        var value = ko.utils.unwrapObservable(valueAccessor());
        if (value) {
            $(element).hide().slideDown();
        } else if (!value) {
            $(element).slideUp();
        }
    }
};

ko.bindingHandlers.starred = {
    init: function (element) {
        $(element).addClass('icon');
    },
    update: function (element, valueAccessor) {
        var value = ko.utils.unwrapObservable(valueAccessor()),
            $element = $(element);
        value = value + '';
        $element.addClass('icon pointer');

        var unselected = 'icon-star-empty';
        var selected = 'icon-star icon-large released';
        var pending = 'icon-refresh icon-spin';
        var error = 'icon-ban-circle';

        var suffix = error;
        if(value === 'false') {
            suffix = unselected;
        } else if(value === 'true') {
            suffix = selected;
        } else if(value === 'pending') {
            suffix = pending;
        }

        $element.removeClass(unselected);
        $element.removeClass(selected);
        $element.removeClass(pending);
        $element.removeClass(error);
        $element.addClass(suffix);
    }
};

ko.bindingHandlers.bootstrapCollapse = {
    init: function (element) {
        $(element).on('click', 'a.accordion-toggle', function () {
            var $a = $(this);
            if (!$a.attr('href')) {
                $a.parent().parent().find('.collapse').collapse('toggle');
            }
        });
    }
};

ko.bindingHandlers.bootstrapTabs = {
    init: function (element) {
        var tabLinkSelector = 'ul.nav > li > a';
        var activate = function () {
            var n = $(tabLinkSelector, element).index(this);
            $(tabLinkSelector, element).parents().removeClass('active');
            $(this).parent().addClass('active');
            $('.tab-pane', element).removeClass('active');
            $('.tab-pane:eq(' + n + ')', element).addClass('active');
        };
        $(element).on('click', tabLinkSelector, activate);
        // Wait for the rest of the element to be rendered before init'ing
        // (bit of a race condition)
        setTimeout(function () {
            $('ul.nav > li.active > a', element).each(activate);
        }, 0);
    }
};

function ValueOrNoneUI(opts) {
    /* Helper used with exitInput/enterInput */
    var self = this;
    var wrapObservable = function (o) {
        if (ko.isObservable(o)) {
            return o;
        } else {
            return ko.observable(o);
        }
    };

    self.messages = opts.messages;
    self.inputName = opts.inputName;
    self.inputCss = opts.inputCss;
    self.inputAttr = opts.inputAttr;
    self.defaultValue = opts.defaultValue;


    self.allowed = wrapObservable(opts.allowed);
    self.inputValue = wrapObservable(opts.value || '');
    self.hasValue = ko.observable(!!self.inputValue());
    self.hasFocus = ko.observable();

    // make the input get preloaded with the defaultValue
    self.hasFocus.subscribe(function (value) {
        if (!self.inputValue()) {
            self.inputValue(self.defaultValue);
        }
    });

    self.value = ko.computed({
        read: function () {
            if (self.hasValue()) {
                return self.inputValue() || '';
            } else {
                return '';
            }
        },
        write: function (value) {
            self.inputValue(value)
        }
    });
    self.setHasValue = function (hasValue, event) {
        var before = self.value(),
            after;
        self.hasValue(hasValue);
        after = self.value();
        if (before !== after) {
            $(event.toElement).change();
        }
    };
    self.enterInput = function (data, event) {
        if (self.allowed()) {
            self.hasFocus(true);
        }
        self.setHasValue(true, event);
    };
    self.exitInput = function (data, event) {
        self.setHasValue(false, event);
        self.value('');
    };
}

function _makeClickHelper(fnName, icon) {
    return {
        init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            var $el = $(element);
            $('<i></i>').addClass(icon).prependTo($el);
            return ko.bindingHandlers.click.init(element, function () {
                return valueAccessor()[fnName];
            }, allBindingsAccessor, viewModel, bindingContext);
        }
    };
}

ko.bindingHandlers.exitInput = _makeClickHelper('exitInput', 'icon icon-remove');
ko.bindingHandlers.enterInput = _makeClickHelper('enterInput', 'icon icon-plus');

ko.bindingHandlers.valueOrNoneUI = {
    init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var opts = valueAccessor(),
            helper;
        opts.messages = opts.messages || {};
        $('span', element).each(function () {
            opts.messages[$(this).data('slug')] = $(this).html();
            $(this).hide();
        });
        helper = new ValueOrNoneUI(opts);
        var subElement = $('<div></div>').attr(
            'data-bind',
            "template: 'value-or-none-ui-template'"
        ).appendTo(element);
        ko.applyBindings(helper, subElement.get(0));
        return {controlsDescendantBindings: true};
    }
};

ko.bindingHandlers.makeHqHelp = {
    init: function (element, valueAccessor) {
        var opts = valueAccessor(),
            name = ko.utils.unwrapObservable(opts.name || $(element).data('title')),
            description = ko.utils.unwrapObservable(opts.description || $(element).data('content')),
            format = ko.utils.unwrapObservable(opts.format);
        COMMCAREHQ.makeHqHelp({
            title: name,
            content: description,
            html: format === 'html'
        }).appendTo(element);
    }
};

ko.bindingHandlers.optstr = {
    /*
        I find this often to be nicer than the built-in 'options' bindingHandler
        optstr: [{label: 'Yes', value: true},  {label: 'No', value: false}]
        optstrValue: 'value' (default)
        optstrText: 'label' (default)
        value: (ko.observable)
     */
    update: function (element, valueAccessor, allBindingsAccessor) {
        var optionObjects = ko.utils.unwrapObservable(valueAccessor());
        var allBindings = allBindingsAccessor();
        var optstrValue = allBindings.optstrValue || 'value';
        var optstrText = allBindings.optstrText || 'label';
        var optionStrings = ko.utils.arrayMap(optionObjects, function (o) {
            return o[optstrValue];
        });
        allBindings.optionsText = function (optionString) {
            for (var i = 0; i < optionObjects.length; i++) {
                if (optionObjects[i][optstrValue] === optionString) {
                    if (typeof optstrText === 'string') {
                        return optionObjects[i][optstrText];
                    } else {
                        return optstrText(optionObjects[i]);
                    }
                }
            }
        };

        return ko.bindingHandlers.options.update(element, function () {
            return optionStrings;
        }, function () {
            return allBindings;
        });
    }
};

ko.bindingHandlers.valueDefault = {
    init: ko.bindingHandlers.value.init,
    update: function (element, valueAccessor, allBindingsAccessor) {
        var value = valueAccessor();
        if (!value()) {
            value(ko.utils.unwrapObservable(allBindingsAccessor()['default']));
        }
        return ko.bindingHandlers.value.update(element, valueAccessor);
    }
};

ko.bindingHandlers.edit = {
    update: function (element, valueAccessor) {
        var editable = ko.utils.unwrapObservable(valueAccessor());
        function getValue(e) {
            if ($(e).is('select')) {
                return $('option[value="' + $(e).val() + '"]', e).text() || $(e).val();
            }
            return $(e).val();
        }
        if (editable) {
            $(element).show();
            $(element).next('.ko-no-edit').hide();
        } else {
            $(element).hide();
            var no_edit = $(element).next('.ko-no-edit');
            if (!no_edit.length) {
                if ($(element).hasClass('code')) {
                    no_edit = $('<code></code>');
                } else {
                    no_edit = $('<span></span>');
                }
                no_edit.addClass('ko-no-edit').insertAfter(element);
            }
            no_edit.text(getValue(element)).removeClass().addClass($(element).attr('class')).addClass('ko-no-edit').addClass('ko-no-edit-' + element.tagName.toLowerCase());
        }
    }
};

ko.bindingHandlers.typeahead = {
    init: function (element, valueAccessor) {
        $(element).autocomplete({
            minLength: 0,
            delay: 0,
            change: function () {
                $(element).change();
            },
            select: function (event, ui) {
                $(element).val(ui.item.value);
                $(element).trigger('textchange');
            }
        }).focus(function () {
            $(element).autocomplete('search', $(element).val())
                .autocomplete('widget').css({
                width: '200px',
                overflow: 'hidden'
            });
        }).on('textchange', function () {
            if ($(element).val()) {
                $(element).change();
            }
        });
    },
    update: function (element, valueAccessor) {
        $(element).autocomplete('option', 'source', ko.utils.unwrapObservable(valueAccessor()));
    }
};

ko.bindingHandlers.multiTypeahead = {
    init: function(element, valueAccessor) { 
        var contacts = valueAccessor();
        $(element).multiTypeahead({ 
            source: contacts
        }).focus();
    }
};

/**
 * A custom knockout binding that replaces the element's contents with a jquery
 * element.
 * @type {{update: update}}
 */
ko.bindingHandlers.jqueryElement = {
    init: function () {
        // This excludes this element from ko.applyBindings
        // which means that whatever controls that element
        // is free to use its own knockout without conflicting
        return {controlsDescendantBindings: true};
    },
    update: function(element, valueAccessor, allBindings, viewModel, bindingContext) {
        $(element).empty();
        $(element).append(ko.unwrap(valueAccessor()));
    }
};

ko.bindingHandlers.__copyPasteSharedInit = function () {
    var offScreen = {top: -10000, left: -10000};
    var hiddenTextarea = $('<textarea></textarea>').css({
        position: 'absolute',
        width: 0,
        height: 0
    }).css(offScreen).appendTo('body');
    var focusTextarea = function ($element, value) {
        hiddenTextarea.css({top: $element.offset().top});
        hiddenTextarea.val(value);
        hiddenTextarea.focus();
        hiddenTextarea.select();
    };
    var unfocusTextarea = function ($element) {
        $element.focus();
        return hiddenTextarea.val();
    };
    // Firefox only fires copy/paste when it thinks it's appropriate
    // Chrome doesn't fire copy/paste after key down has changed the focus
    // So we need implement both copy/paste as catching keystrokes Ctrl+C/V
    $(document).on('copy paste keydown', function (e) {
        var $element, callback;
        if (e.type === 'copy' || e.metaKey && String.fromCharCode(e.keyCode) === 'C') {
            $element = $(':focus');
            callback = $element.data('copyCallback');
            if (callback) {
                focusTextarea($element, callback());
                setTimeout(function () {
                    unfocusTextarea($element);
                }, 0);
            }
        } else if (e.type === 'paste' || e.metaKey && String.fromCharCode(e.keyCode) === 'V') {
            $element = $(':focus');
            callback = $element.data('pasteCallback');
            if (callback) {
                focusTextarea($element);
                setTimeout(function () {
                    var pasteValue = unfocusTextarea($element);
                    // part of the above hack
                    // on chrome this gets called twice,
                    // the first time with a blank value
                    if (pasteValue) {
                        callback(pasteValue);
                    }
                }, 0);
            }
        }
    });

    // only ever call this function once
    ko.bindingHandlers.__copyPasteSharedInit = function () {};
};

ko.bindingHandlers.copy = {
    init: function (element, valueAccessor) {
        ko.bindingHandlers.__copyPasteSharedInit();
        $(element).data('copyCallback', valueAccessor());
    }
};

ko.bindingHandlers.paste = {
    init: function (element, valueAccessor) {
        ko.bindingHandlers.__copyPasteSharedInit();
        var callback = valueAccessor();
        $(element).data('pasteCallback', valueAccessor());
    }
};
