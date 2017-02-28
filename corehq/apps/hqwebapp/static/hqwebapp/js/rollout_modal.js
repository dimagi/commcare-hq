hqDefine("hqwebapp/js/rollout_modal.js", function() {
    $(function() {
        $('.rollout-modal').modal({
            backdrop: 'static',
            keyboard: false,
            show: true,
        })/*.on('hide.bs.modal', function () {
            window.location = hqImport('hqwebapp/js/urllib.js').reverse('default_app');
        })*/;
    });
});
