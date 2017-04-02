hqDefine('app_manager/js/supported-languages.js', function () {
    function Language(langcode, languages) {
        var self = this;
        this.langcode = ko.observable(langcode);
        this.originalLangcode = ko.observable(langcode);
        this.message_content = ko.observable('');
        this.show_error = ko.observable();
        this.languages = languages;
        this.message = ko.computed(function () {
            if (self.message_content() === '') {
                if (self.langcode()) {
                    var lang = self.langcode().toLowerCase();
                    $.getJSON('/langcodes/langs.json', {term: lang}, function(res) {
                        var index = _.map(res, function(r) { return r.code; }).indexOf(lang);
                        if (index === -1) {
                            self.message_content(gettext("Warning: unrecognized language"));
                            self.show_error(true);
                        } else {
                            self.message_content(res[index].name);
                            self.show_error(false);
                        }
                    });
                }
            }
            return self.message_content();
        });

        this.isDefaultLang = ko.computed(function () {
            return self.languages()[0] === self;
        });
    }
    function SupportedLanguages(options) {
        var langs = options.langs;
        var saveURL = options.saveURL;
        var validate = options.validate;
        var self = this;

        this.addLanguageDisabled = ko.observable(false);
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
            unsavedMessage: gettext("You have unsaved changes in your supported languages"),
            save: function () {
                var message = self.validateGeneral();
                if (message) {
                    alert(message);
                    return;
                }
                for (var i = 0; i < self.languages().length; i++) {
                    if (self.validateLanguage(self.languages()[i])) {
                        alert(gettext("There are errors in your configuration"));
                        return;
                    }
                }
                var langs = [];
                var rename = {};
                ko.utils.arrayForEach(self.languages(), function (language) {
                    langs.push(language.langcode());
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
                    }),
                    success: function (data) {
                        var i;
                        for (i = 0; i < langs.length; i++) {
                            if (langs[i] != data[i]) {
                                throw "There was an error saving.";
                            }
                        }
                        self.removedLanguages.removeAll();
                        self.addLanguageDisabled(false);
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
        function newLanguage(langcode) {
            var language = new Language(langcode, self.languages);
            language.langcode.subscribe(changeSaveButton);
            language.langcode.subscribe(function () { self.validateLanguage(language); });
            return language;
        }
        this.addLanguage = function () {
            self.languages.push(newLanguage());
            this.addLanguageDisabled(true);
            self._seen(true);
        };
        this.removeLanguage = function (language) {
            self.languages.remove(language);
            self.removedLanguages.push(language);
        };
        this.unremoveLanguage = function (language) {
            self.removedLanguages.remove(language);
            self.languages.push(language);
        };
        for (var i = 0; i < langs.length; i += 1) {
            var language = newLanguage(langs[i]);
            self.languages.push(language);
        }
        this.languages.subscribe(changeSaveButton);

        this.canSortLanguages = ko.computed(function () {
             return self.languages().length > 1;
        });

        this.validateGeneral = function () {
            var message = "";
            if (!validate) {
                return "";
            }
            if (!self.languages().length) {
                message = gettext("You must have at least one language");
            }
            return message;
        };

        this.validateLanguage = function (language) {
            if (!validate) {
                language.message_content("");
                return "";
            }
            var message = "";
            if (!language) {
                message = gettext("Please enter language");
            } else if (!/^[a-z]{2,3}(-[a-z]*)?$/.exec(language.langcode())) {
                message = gettext("Invalid language code");
            }
            for (var i = 0; i < self.languages().length; i++) {
                self.languages()[i].langcode();
                self.languages()[i].originalLangcode();
                if (message || language == self.languages()[i]) {
                    continue;
                } else if (language.langcode() === self.languages()[i].langcode()) {
                    message = gettext("Language appears twice");
                } else if (language.originalLangcode() === self.languages()[i].originalLangcode()) {
                    message = gettext("This conflicts with a current language");
                }
            }
            language.message_content(message);
            language.show_error(message);
            return message;
        };
    }
    return {SupportedLanguages: SupportedLanguages};
});
