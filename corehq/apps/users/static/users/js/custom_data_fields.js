/**
 *  This file defines a model for editing custom data fields while creating or editing a mobile user.
 */
hqDefine("users/js/custom_data_fields", [
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/select2_knockout_bindings.ko',     // selects2 for fields
    'hqwebapp/js/bootstrap3/widgets',      // select2 for user fields profile
], function (
    ko,
    _,
    assertProperties
) {
    var fieldModel = function (options) {
        return {
            value: ko.observable(options.value),
            previousValue: ko.observable(options.value),    // save user-entered value
            disable: ko.observable(!!false),
        };
    };

    var customDataFieldsEditor = function (options) {
        assertProperties.assertRequired(options, ['profiles', 'slugs', 'profile_slug'], ['user_data']);
        options.user_data = options.user_data || {};
        var self = {};

        self.profiles = _.indexBy(options.profiles, 'id');
        self.profile_slug = options.profile_slug;
        self.slugs = options.slugs;

        var originalProfileFields = {},
            originalProfileId,
            originalProfile;
        if (options.user_data) {
            originalProfileId = options.user_data[options.profile_slug];
            if (originalProfileId) {
                originalProfile = self.profiles[originalProfileId];
                if (originalProfile) {
                    originalProfileFields = originalProfile.fields;
                }
            }
        }
        _.each(self.slugs, function (slug) {
            self[slug] = fieldModel({
                value: options.user_data[slug] || originalProfileFields[slug],
                disable: !!originalProfileFields[slug],
            });
        });

        self.serialize = function () {
            var data = {};
            data[self.profile_slug] = self[self.profile_slug].value();
            _.each(self.slugs, function (slug) {
                data[slug] = self[slug].value();
            });
            return data;
        };

        self[self.profile_slug] = fieldModel({value: originalProfileId});
        self[self.profile_slug].value.subscribe(function (newValue) {
            var fields = {};
            if (newValue) {
                fields = self.profiles[newValue].fields;
            }
            _.each(self.slugs, function (slug) {
                var field = self[slug];
                if (Object.prototype.hasOwnProperty.call(fields, slug)) {
                    if (!field.disable()) {
                        field.previousValue(field.value());
                    }
                    field.value(fields[slug]);
                    field.disable(true);
                } else {
                    if (field.disable()) {
                        field.value(field.previousValue());
                    }
                    field.disable(false);
                }
            });
        });

        return self;
    };

    return {
        customDataFieldsEditor: customDataFieldsEditor,
    };
});
