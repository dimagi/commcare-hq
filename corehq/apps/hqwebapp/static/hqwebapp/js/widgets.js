hqDefine("hqwebapp/js/widgets", [
    'jquery',
    'select2-3.5.2-legacy/select2',
], function($) {
    $(function() {
        _.each($(".hqwebapp-autocomplete"), function(input) {
            var $input = $(input);
            $input.select2({
                multiple: true,
                tags: $input.data("choices"),
            });
        });
    });
});
