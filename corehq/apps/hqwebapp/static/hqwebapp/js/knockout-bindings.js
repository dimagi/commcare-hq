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
    init: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        // based on http://www.knockmeout.net/2011/05/dragging-dropping-and-sorting-with.html
        var list = valueAccessor();
        $(element).sortable({
            handle: '.sortable-handle',
            update: function(event, ui) {
                var parent = ui.item.parent();
                var oldPosition = parseInt(ui.item.data('order'), 10);
                var newPosition = ko.utils.arrayIndexOf(parent.children(), ui.item.get(0));
                var item = list()[oldPosition];
                // this is voodoo to me, but I have to remove the ui item from its new position
                // and *not replace* it in its original position for all the foreach mechanisms to work correctly
                // I found this by trial and error
                ui.item.detach();
                //remove the item and add it back in the right spot
                if (newPosition >= 0) {
                    list.remove(item);
                    list.splice(newPosition, 0, item);
                }
            }
        });
        return ko.bindingHandlers.foreach.init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
    },
    update: function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var ret = ko.bindingHandlers.foreach.update(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        $(element).children().each(function (i) {
            $(this).data('order', "" + i);
        });
        return ret;
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
            saveButton = SaveButton.init({
                save: function () {
                    saveButton.ajax(saveOptions());
                }
            });
        saveButton.ui.appendTo(element);
        element.saveButton = saveButton;
    },
    update: function (element, valueAccessor) {
        var state = ko.utils.unwrapObservable(valueAccessor());
        element.saveButton.setStateWhenReady(state);
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
        var ajaxSrc = valueAccessor(),
            modal = $('<div></div>').addClass('jqmWindow').appendTo('body'),
            newValueAccessor = function () {
                var clickAction = function () {
                    modal.jqm({ajax: ajaxSrc}).jqmShow();
                };
                return clickAction;

            };
        ko.bindingHandlers.click.init(element, newValueAccessor, allBindingsAccessor, viewModel, bindingContext);
//            $('#odk-install-placeholder').jqm({ajax: '@href', trigger: 'a.odk_install',
//            ajaxText: "Please wait while we load that for you..." });
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
        $(element).addClass('star');
    },
    update: function (element, valueAccessor) {
        var value = ko.utils.unwrapObservable(valueAccessor()),
            $element = $(element);
        $element.addClass('star');

        $element.removeClass('star-false');
        $element.removeClass('star-true');
        $element.removeClass('star-pending');
        $element.removeClass('star-error');
        $element.addClass('star-' + value);
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
        self.setHasValue(true, event);
        if (self.allowed()) {
            self.hasFocus(true);
        }
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