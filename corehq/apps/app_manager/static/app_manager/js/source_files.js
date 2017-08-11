/* globals hqDefine */
hqDefine('app_manager/js/source_files.js', function() {
    $(function(){
        $('.toggle-next').click(function(e){
            e.preventDefault();
            $(this).parents('tr').next('tr').toggleClass("hide");
        });
    
        var current_version = hqImport('hqwebapp/js/initial_page_data.js').get('current_version'),
            built_versions = hqImport('hqwebapp/js/initial_page_data.js').get('built_versions'),
            $form = $("#compare-form"),
            $input = $form.find("input");
    
        built_versions = _.sortBy(_.filter(built_versions, function(v) {
            return v.version != current_version;
        }), function(v) { return parseInt(v.version); }).reverse();
        version_map = _.indexBy(built_versions, 'version');
    
        $input.select2({
            data: _.map(built_versions, function(v) {
                return {
                    id: v.version,
                    text: v.version + ": " + (v.comment || "no comment"),
                };
            }),
        });
    
        $form.find("button").click(function() {
            var version = $input.val();
            if (!version) {
                alert("Please enter a version to compare");
                return;
            } else if (!version_map[version]) {
                alert(version + " is not a valid version");
                return;
            }
            window.location = hqImport('hqwebapp/js/initial_page_data.js').reverse('diff', version_map[version].build_id);
        });
    });
});
