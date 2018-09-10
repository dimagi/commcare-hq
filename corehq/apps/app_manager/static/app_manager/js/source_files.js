/* globals hqDefine */
hqDefine('app_manager/js/source_files',[
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function($, _, initialPageData) {
    $(function(){
        $('.toggle-next').click(function(e){
            e.preventDefault();
            $(this).parents('tr').next('tr').toggleClass("hide");
        });
    
        var currentVersion = initialPageData.get('current_version'),
            builtVersions = initialPageData.get('built_versions'),
            $form = $("#compare-form"),
            $input = $form.find("input");

        builtVersions = _.sortBy(_.filter(builtVersions, function(v) {
            return v.version != currentVersion;
        }), function(v) { return parseInt(v.version); }).reverse();
        var versionMap = _.indexBy(builtVersions, 'version');
    
        $input.select2({
            data: _.map(builtVersions, function(v) {
                return {
                    id: v.version,
                    text: v.version + ": " + (v.comment || "no comment"),
                };
            }),
        });
    
        $form.find("button").click(function () {
            var version = $input.val();
            if (!version) {
                alert("Please enter a version to compare");
                return;
            } else if (!versionMap[version]) {
                alert(version + " is not a valid version");
                return;
            }
            window.location = initialPageData.reverse('diff', versionMap[version].build_id);
        });
    });
});
