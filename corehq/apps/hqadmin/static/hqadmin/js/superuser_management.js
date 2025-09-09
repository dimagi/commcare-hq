hqDefine('hqadmin/js/superuser_management', [
    'jquery',
], function (
    $,
) {
    $(function () {
        const $isSuperUser = $('#privileges').find('input[value="is_superuser"]');
        const $featureFlagsCategories = $('#feature_flag_edit_permissions').find('input[type="checkbox"]');

        function updateFeatureFlagsSelection() {
            const isSuperuser = $isSuperUser.is(':checked');
            $featureFlagsCategories.prop('disabled', !isSuperuser);
            if (!isSuperuser) {
                $featureFlagsCategories.prop('checked', false);
            }
        }

        updateFeatureFlagsSelection();
        $isSuperUser.on('change', updateFeatureFlagsSelection);
    });
});
