// knockout_bindings is required sortable used here 'app_manager/partials/settings/supported_languages.html#L4'
hqDefine('app_manager/js/supported_languages',[
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/main",
    "hqwebapp/js/bootstrap3/knockout_bindings.ko",
], function ($, ko, _, initialPageData, hqMain) {
    function Language(langcode, languages) {
        var self = {};
        self.langcode = ko.observable(langcode);
        self.originalLangcode = ko.observable(langcode);
        self.message_content = ko.observable('');
        self.show_error = ko.observable();
        self.languages = languages;
        self.message = ko.computed(function () {
            if (self.langcode()) {
                var lang = self.langcode().toLowerCase();
                $.getJSON('/langcodes/langs.json', {term: lang}, function (res) {
                    var index = _.map(res, function (r) { return r.code; }).indexOf(lang);
                    if (index === -1) {
                        self.message_content(gettext("Warning: unrecognized language"));
                        self.show_error(true);
                    } else if (!self.show_error()) {
                        self.message_content(res[index].name);
                        self.show_error(false);
                    }
                });
            }

            return self.message_content();
        });
        self.originalLangcodeMessage = ko.computed(function () {
            if (!self.originalLangcode()) {
                return '';
            }

            return "(" + _.template("originally <%- originalLanguage %>")({
                originalLanguage: self.originalLangcode(),
            }) + ")";
        });

        self.isDefaultLang = ko.computed(function () {
            return self.languages()[0] === self;
        });
        return self;
    }
    function SupportedLanguages(options) {
        var langs = options.langs;
        var saveURL = options.saveURL;
        var validate = options.validate;
        var self = {};

        self.addLanguageDisabled = ko.observable(false);
        self._seen = ko.observable(false);
        self.seen = ko.computed({
            read: function () {
                return self._seen();
            },
            write: function () {
                self._seen(true);
            },
        });
        self.saveButton = hqMain.initSaveButton({
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
                        smart_lang_display: self.smartLangDisplay,
                    }),
                    success: function (data) {
                        var i;
                        for (i = 0; i < langs.length; i++) {
                            if (langs[i] !== data[i]) {
                                throw "There was an error saving.";
                            }
                        }
                        self.removedLanguages.removeAll();
                        self.addLanguageDisabled(false);
                        ko.utils.arrayForEach(self.languages(), function (language) {
                            language.originalLangcode(language.langcode());
                        });
                    },
                });
            },
        });

        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };
        var smartLangDisplayEnabled = initialPageData.get("smart_lang_display_enabled");
        self.smartLangDisplay = ko.observable(smartLangDisplayEnabled);
        self.smartLangDisplay.subscribe(changeSaveButton);

        self.languages = ko.observableArray([]);
        self.removedLanguages = ko.observableArray([]);
        function newLanguage(langcode) {
            var language = Language(langcode, self.languages);
            language.langcode.subscribe(changeSaveButton);
            language.langcode.subscribe(function () { self.validateLanguage(language); });
            return language;
        }
        self.addLanguage = function () {
            self.languages.push(newLanguage());
            self.addLanguageDisabled(true);
            self._seen(true);
        };
        self.removeLanguage = function (language) {
            self.languages(_.without(self.languages(), language));
            self.removedLanguages.push(language);
        };
        self.setAsDefault = function (language) {
            self.languages(_.without(self.languages(), language));
            self.languages.unshift(language);
        };
        self.unremoveLanguage = function (language) {
            self.removedLanguages(_.without(self.removedLanguages(), language));
            self.languages.push(language);
        };
        for (var i = 0; i < langs.length; i += 1) {
            var language = newLanguage(langs[i]);
            self.languages.push(language);
        }
        self.languages.subscribe(changeSaveButton);

        self.canSortLanguages = ko.computed(function () {
            return self.languages().length > 1;
        });

        self.validateGeneral = function () {
            var message = "";
            if (!validate) {
                return "";
            }
            if (!self.languages().length) {
                message = gettext("You must have at least one language");
            }
            return message;
        };

        self.validateLanguage = function (language) {
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
                if (message || language === self.languages()[i]) {
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
        self.showSmartLangDisplayOption = ko.computed(function () {
            return self.languages().length > 2;
        });
        return self;
    }
    return {SupportedLanguages: SupportedLanguages};
});
