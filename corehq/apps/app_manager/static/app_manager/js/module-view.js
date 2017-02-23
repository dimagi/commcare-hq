$(function () {
    $(function () {
        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport('hqwebapp/js/urllib.js').reverse('validate_module_for_build'));
    });
    $(function() {
        // show display style options only when module configured to show module and then forms
        var $menu_mode = $('#put_in_root');
        var $display_style_container = $('#display_style_container');
        var update_display_view = function() {
            if($menu_mode.val() == 'false') {
                $display_style_container.show();
            } else {
                $display_style_container.hide();
            }
        }
        update_display_view()
        $menu_mode.on('change', update_display_view)
    });
});
