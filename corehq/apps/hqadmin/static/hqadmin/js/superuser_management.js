hqDefine('hqadmin/js/superuser_management', [
    'jquery',
], function (
    $,
) {
    $(function () {
        let $privileges = $('#privileges');
        let $featureFlagsCategories = $('#feature_flag_edit_permissions');

        function updateFeatureFlags() {
            let isSuperuser = $privileges.find('input[value="is_superuser"]').is(':checked');
            $featureFlagsCategories.find('input[type="checkbox"]').prop('disabled', !isSuperuser);
            if (!isSuperuser) {
                $featureFlagsCategories.find('input[type="checkbox"]').prop('checked', false);
            }
        }

        updateFeatureFlags();
        $privileges.on('change', updateFeatureFlags);
    });
});
