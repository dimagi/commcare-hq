hqDefine('app_manager/js/preview_app.js', function() {

    var initializePreviewButton = function() {
        var $previewBtn = $('.preview-app-btn'),
            $previewPhoneContainer = $('.preview-phone-container');
        $previewBtn.click(function(e) {
            $previewPhoneContainer.toggleClass('hide');
        });
    };

    return {
        initializePreviewButton: initializePreviewButton,
    };
});
