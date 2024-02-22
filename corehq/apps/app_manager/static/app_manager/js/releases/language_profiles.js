hqDefine('app_manager/js/releases/language_profiles', function () {
    var _p = {};
    _p.profileUrl = 'profiles/';

    var profileModel = function (profileLangs, name, id, practiceUser, latestEnabledVersions) {
        var self = {};
        self.id = id;
        self.langs = ko.observableArray(profileLangs);
        self.name = ko.observable(name);
        self.defaultLang = ko.observable(profileLangs[0]);
        self.practiceUser = ko.observable(practiceUser);
        self.latestEnabledVersion = ko.observable(latestEnabledVersions[self.id]);
        return self;
    };

    function setProfileUrl(url) {
        _p.profileUrl = url;
    }

    var profileManager = function (appProfiles, appLangs, enablePracticeUsers, practiceUsers, latestEnabledVersions) {
        var self = {};
        self.latestEnabledVersions = latestEnabledVersions;
        self.app_profiles = ko.observableArray([]);
        self.app_langs = appLangs;
        self.enable_practice_users = enablePracticeUsers;
        self.practice_users = [{'id': '', 'text': ''}].concat(practiceUsers);
        self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
            unsavedMessage: gettext("You have unsaved changes to your application profiles"),
            save: function () {
                var postProfiles = [];
                _.each(self.app_profiles(), function (element) {
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
                    error: function () {
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
            'placeholder': gettext(practiceUsers.length > 0 ? 'Select a user' : 'No practice mode mobile workers available'),
        };
        self.addProfile = function (langs, name, id, practiceUser) {
            var profile = profileModel(langs, name, id, practiceUser, self.latestEnabledVersions);
            profile.name.subscribe(changeSaveButton);
            profile.langs.subscribe(changeSaveButton);
            profile.defaultLang.subscribe(changeSaveButton);
            if (self.enable_practice_users) {
                profile.practiceUser.subscribe(changeSaveButton);
            }
            self.app_profiles.push(profile);
        };
        _.each(appProfiles, function (value, key) {
            self.addProfile(value.langs, value.name, key, value.practice_mobile_worker_id || '');
        });
        self.newProfile = function () {
            self.addProfile([], '', '', '');
            var index = self.app_profiles().length - 1;
            _.delay(function () {
                $('#profile-' + index).select2();
                $('#practice-user-' + index).select2(select2config);
            });
        };
        if (!self.app_profiles()) {
            self.newProfile();
        }
        self.removeProfile = function (profile) {
            self.app_profiles.remove(profile);
        };
        self.app_profiles.subscribe(changeSaveButton);
        _.delay(function () {
            $('.language-select').select2();
            $('.practice-user').select2(select2config);
        });
        return self;
    };

    return {
        profileManager: profileManager,
        setProfileUrl: setProfileUrl,
    };
});
