/* globals hqDefine, ko, COMMCAREHQ */
hqDefine('app_manager/js/language-profiles.js', function () {
    function Profile(profile_langs, name, id) {
        this.id = id;
        this.langs = ko.observableArray(profile_langs);
        this.name = ko.observable(name);
        this.defaultLang = ko.observable(profile_langs[0]);
    }
    function ProfileManager(app_profiles, app_langs) {
        var self = this;
        this.app_profiles = ko.observableArray([]);
        this.app_langs = app_langs;
        this.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: gettext("You have unsaved changes to your application profiles"),
            save: function() {
                var postProfiles = [];
                _.each(self.app_profiles(), function(element) {
                    // move default lang to first element of array
                    var postLangs = element.langs();
                    postLangs.splice(postLangs.indexOf(element.defaultLang()), 1);
                    postLangs.unshift(element.defaultLang());
                    postProfiles.push({
                        'name': element.name(),
                        'langs': postLangs,
                        'id': element.id,
                    });
                });
                self.saveButton.ajax({
                    url: 'profiles/', // this should resolve to LanguageProfilesView
                    type: 'post',
                    data: JSON.stringify({'profiles': postProfiles}),
                    error: function() {
                        throw gettext("There was an error saving");
                    },
                });
            },
        });
        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };
        this.addProfile = function(langs, name, id) {
            var profile = new Profile(langs, name, id);
            profile.name.subscribe(changeSaveButton);
            profile.langs.subscribe(changeSaveButton);
            profile.defaultLang.subscribe(changeSaveButton);
            self.app_profiles.push(profile);
        };
        _.each(app_profiles, function(value, key) {
            self.addProfile(value.langs, value.name, key);
        });
        this.newProfile = function() {
            self.addProfile([], '', '');
            var index = self.app_profiles().length - 1;
            _.delay(function() {
                $('#profile-' + index).select2();
            });
        };
        if (!self.app_profiles()) {
            self.newProfile();
        }
        this.removeProfile = function(profile) {
            self.app_profiles.remove(profile);
        };
        this.app_profiles.subscribe(changeSaveButton);
        _.delay(function() {
            $('.language-select').select2();
        });
    }
    return {ProfileManager: ProfileManager};
});
