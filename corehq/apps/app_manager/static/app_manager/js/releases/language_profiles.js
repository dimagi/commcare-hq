/* globals hqDefine, hqImport, ko */
hqDefine('app_manager/js/releases/language_profiles', function () {
    var _p = {};
    _p.profileUrl = 'profiles/';

    function Profile(profile_langs, name, id, practiceUser) {
        this.id = id;
        this.langs = ko.observableArray(profile_langs);
        this.name = ko.observable(name);
        this.defaultLang = ko.observable(profile_langs[0]);
        this.practiceUser = ko.observable(practiceUser);
    }

    function setProfileUrl(url) {
        _p.profileUrl = url;
    }

    function ProfileManager(app_profiles, app_langs, enable_practice_users, practice_users) {
        var self = this;
        this.app_profiles = ko.observableArray([]);
        this.app_langs = app_langs;
        this.enable_practice_users = enable_practice_users;
        this.practice_users = [{'id': '', 'text': ''}].concat(practice_users);
        this.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
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
                        'practice_user_id': element.practiceUser(),
                    });
                });
                self.saveButton.ajax({
                    url: _p.profileUrl, // this should resolve to LanguageProfilesView
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
        var select2config = {
            'allowClear': true,
            'width': '100%',
            'placeholder': gettext(practice_users.length > 0 ? 'Select a user': 'No practice mode mobile workers available'),
        };
        this.addProfile = function(langs, name, id, practiceUser) {
            var profile = new Profile(langs, name, id, practiceUser);
            profile.name.subscribe(changeSaveButton);
            profile.langs.subscribe(changeSaveButton);
            profile.defaultLang.subscribe(changeSaveButton);
            if (self.enable_practice_users){
                profile.practiceUser.subscribe(changeSaveButton);
            }
            self.app_profiles.push(profile);
        };
        _.each(app_profiles, function(value, key) {
            self.addProfile(value.langs, value.name, key, value.practice_mobile_worker_id || '');
        });
        this.newProfile = function() {
            self.addProfile([], '', '', '');
            var index = self.app_profiles().length - 1;
            _.delay(function() {
                $('#profile-' + index).select2();
                $('#practice-user-' + index).select2(select2config);
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
            $('.practice-user').select2(select2config);
        });
    }
    return {
        ProfileManager: ProfileManager,
        setProfileUrl: setProfileUrl,
    };
});
