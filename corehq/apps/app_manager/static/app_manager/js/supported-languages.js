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
    update: function (element, valueAccessor) {
        var value = ko.utils.unwrapObservable(valueAccessor());
        var span = $('span', element);
        var iconTrue = 'icon-ok', iconFalse = '';

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
            return $('<input/>');
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

var SupportedLanguages = (function () {
    function Language(langcode, deploy) {
        var self = this;
        this.langcode = ko.observable(langcode);
        this.originalLangcode = ko.observable(langcode);
        this.deploy = ko.observable(deploy === undefined ? true : deploy);
    }
    function SupportedLanguages(options) {
        var langs = options.langs;
        var buildLangs = options.buildLangs;
        var saveURL = options.saveURL;
        var validate = options.validate;
        var self = this;

        this.editing = ko.observable(options.edit);
        this._seen = ko.observable(false);
        this.seen = ko.computed({
            read: function () {
                return self._seen();
            },
            write: function () {
                self._seen(true);
            }
        });
        this.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unsaved changes in your supported languages",
            save: function () {
                var message = self.validateGeneral();
                if (message) {
                    alert(message);
                    return;
                }
                for (var i = 0; i < self.languages().length; i++) {
                    if (self.validateLanguage(self.languages()[i])) {
                        alert("There are errors in your configuration");
                        return;
                    }
                }
                var langs = [];
                var buildLangs = [];
                var rename = {};
                ko.utils.arrayForEach(self.languages(), function (language) {
                    langs.push(language.langcode());
                    if (language.deploy()) {
                        buildLangs.push(language.langcode());
                    }
                    if (language.originalLangcode()) {
                        rename[language.originalLangcode()] = language.langcode();
                    }
                });
                self.saveButton.ajax({
                    url: saveURL,
                    type: 'post',
                    dataType: 'json',
                    data: ko.toJSON({
                        langs: langs,
                        rename: rename,
                        build: buildLangs
                    }),
                    success: function (data) {
                        var i;
                        for (i = 0; i < langs.length; i++) {
                            if (langs[i] != data[i]) {
                                throw "There was an error saving.";
                            }
                        }
                        self.removedLanguages.removeAll();
                        ko.utils.arrayForEach(self.languages(), function (language) {
                            language.originalLangcode(language.langcode());
                        });
                    }
                });
            }
        });

        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };

        this.languages = ko.observableArray([]);
        this.removedLanguages = ko.observableArray([]);
        function newLanguage(langcode, deploy) {
            var language = new Language(langcode, deploy);
            language.langcode.subscribe(changeSaveButton);
            language.deploy.subscribe(changeSaveButton);
            return language;
        }
        this.addLanguage = function () {
            self.languages.push(newLanguage());
            self._seen(true);
        };
        this.removeLanguage = function (language) {
            self.languages.remove(language);
            if (language.originalLangcode()) {
                self.removedLanguages.push(language);
            }
        };
        this.unremoveLanguage = function (language) {
            self.removedLanguages.remove(language);
            self.languages.push(language);
        };
        for (var i = 0; i < langs.length; i += 1) {
            var deploy = buildLangs.indexOf(langs[i]) !== -1;
            var language = newLanguage(langs[i], deploy);
            self.languages.push(language);
        }
        this.languages.subscribe(changeSaveButton);


        this.validateGeneral = function () {
            var message = "";
            if (!validate) {
                return "";
            }
            if (!self.languages().length) {
                message = "You must have at least one language";
            }
            var totalDeploy = 0;
            for (var i = 0; i < self.languages().length; i++) {
                if (self.languages()[i].deploy()) {
                    totalDeploy++;
                }
            }
            if (!message && !totalDeploy) {
                message = "You must deploy at least one language";
            }
            return message;
        };
        this.validateLanguage = function (language) {
            if (!validate) {
                return "";
            }
            var message = "";
            if (!language.langcode()) {
                message = "Please enter language";
            } else if (!/^[a-z]{2,3}(-[a-z]*)?$/.exec(language.langcode())) {
                message = "Invalid language code";
            }
            for (var i = 0; i < self.languages().length; i++) {
                self.languages()[i].langcode();
                self.languages()[i].originalLangcode();
                if (message || language == self.languages()[i]) {
                    continue;
                } else if (language.langcode() === self.languages()[i].langcode()) {
                    message = "Language appears twice";
                } else if (language.langcode() === self.languages()[i].originalLangcode()) {
                    message = "This conflicts with a current language";
                }
            }
            return message;
        };
    }
    return SupportedLanguages;
}());