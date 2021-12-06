/**
 * Model for parent/child selection in case list config.
 *
 * This lets app builders configure a case list to show a case list
 * for a different menu that uses this menu's case type's parent
 * case type. The user will select a parent case from that case list
 * and then see the case list for this menu filtered down to children
 * of that selected parent case.
 *
 * This UI also supports the NON_PARENT_MENU_SELECTION feature flag,
 * which allows app builders to configure the case list so that
 * users will be presented with another menu's case list and select
 * a case before proceeding to the curent menu's case list, but the
 * current menu's case list will not be filtered to children of that
 * first case. This first case will just be available to forms.
 * This is used for deduplication workflows.
 */
hqDefine("app_manager/js/details/parent_select", function () {
    return function (init) {
        var self = {};
        var defaultModule = _(init.parentModules).findWhere({
            is_parent: true,
        });
        self.moduleId = ko.observable(init.moduleId || (defaultModule ? defaultModule.unique_id : null));
        self.allCaseModules = ko.observable(init.allCaseModules);
        self.parentModules = ko.observable(init.parentModules);
        self.lang = ko.observable(init.lang);
        self.langs = ko.observable(init.langs);
        self.enableOtherOption = hqImport('hqwebapp/js/toggles').toggleEnabled('NON_PARENT_MENU_SELECTION');

        self.selectOptions = [
            {id: 'none', text: gettext('None')},
            {id: 'parent', text: gettext('Parent')},
        ];
        if (self.enableOtherOption) {
            self.selectOptions.push(
                {id: 'other', text: gettext('Other')}
            );
        }
        var selectMode = init.active ? (init.relationship === 'parent' ? 'parent' : 'other') : 'none';
        if (self.enableOtherOption) {
            self.selectMode = ko.observable(selectMode);
            self.active = ko.computed(function () {
                return (self.selectMode() !== 'none');
            });
        } else {
            self.active = ko.observable(init.active);
            self.selectMode = ko.computed(function () {
                return self.active ? 'parent' : 'none';
            });
        }
        self.relationship = ko.computed(function () {
            return (self.selectMode() === 'parent' || self.selectMode() === 'none') ? 'parent' : null ;
        });

        function getTranslation(name, langs) {
            var firstLang = _(langs).find(function (lang) {
                return name[lang];
            });
            return name[firstLang];
        }
        self.dropdownModules = ko.computed(function () {
            return (self.selectMode() === 'parent') ? self.parentModules() : self.allCaseModules();
        });
        self.hasError = ko.computed(function () {
            return !_.contains(_.pluck(self.dropdownModules(), 'unique_id'), self.moduleId());
        });
        self.moduleOptions = ko.computed(function () {
            var options = _(self.dropdownModules()).map(function (module) {
                var STAR = '\u2605',
                    SPACE = '\u3000';
                var marker = (module.is_parent ? STAR : SPACE);
                return {
                    value: module.unique_id,
                    label: marker + ' ' + getTranslation(module.name, [self.lang()].concat(self.langs())),
                };
            });
            if (self.hasError()) {
                options.unshift({
                    value: '',
                    label: gettext('Unknown menu'),
                });
            }
            return options;
        });
        return self;
    };
});