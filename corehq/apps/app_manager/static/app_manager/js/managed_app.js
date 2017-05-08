$(function () {
    var initial_page_data = hqImport('hqwebapp/js/initial_page_data.js').get,
        init = hqImport('app_manager/js/app_manager.js').init,
        v2 = COMMCAREHQ.toggleEnabled('APP_MANAGER_V2'),
        app = initial_page_data('app_subset');

    init({
        appVersion: app.version || -1,
        commcareVersion: String(app.commcare_minor_release),
        latestCommcareVersion: initial_page_data('latest_commcare_version') || null,
    });

    $('.btn-langcode-preprocessed').each( function () {
        langcodeTag.button_tag($(this), $(this).text());
        if ($(this).hasClass('langcode-input')) {
            var $langcodeInput = $(this).parent().find("input");
            var that = this;
            if ($langcodeInput) {
                $langcodeInput.change(function () {
                    if ($(this).val() == "")
                        $(that).show();
                    else
                        $(that).hide();
                });
            }
        }
    });

    if (app.doc_type === 'Application') {
        $('[data-toggle="tooltip"]').tooltip();
        if (v2) {
            $('.edit-form-li').each(function () {
                var $this = $(this);
                if (initial_page_data('formdesigner') || !$this.hasClass("active")) {
                    var $pencil = $this.find('.edit-form-pencil');
                    $pencil.addClass('no-data');
                    $this.hover(function() {
                        $pencil.removeClass('no-data');
                    }, function() {
                        $pencil.addClass('no-data');
                    });
                }
            });
        } else {
            $('.edit-form-pencil').tooltip({
                title: gettext("Edit in form builder"),
                placement: 'auto'
            });

            $('.edit-form-li').each(function () {
                var $this = $(this);
                if (!initial_page_data('formdesigner') || !$this.hasClass("active")) {
                    var $pencil = $this.find('.edit-form-pencil');
                    $pencil.addClass('no-data');
                    $this.hover(function() {
                        $pencil.removeClass('no-data');
                    }, function() {
                        $pencil.addClass('no-data');
                    });
                }
            });
        }
    }

    // https://github.com/twitter/bootstrap/issues/6122
    // this is necessary to get popovers to be able to extend
    // outside the borders of their containing div
    //
    // http://manage.dimagi.com/default.asp?183618
    // Firefox 40 considers hovering on a select a mouseleave event and thus kills the select
    // dropdown. The focus and blur events are to ensure that we do not trigger overflow hidden
    // if we are in a select
    var inSelectElement = false,
        $tabContent = $('.tab-content');
    $tabContent.css('overflow', 'visible');
    $tabContent.on('mouseenter', '.collapse', function () {
        $(this).css('overflow','visible');
    });
    $tabContent.on('mouseleave', '.collapse', function () {
        if (inSelectElement) { return; }
        $(this).css('overflow','hidden');
    });
    $tabContent.on('focus', '.collapse', function() {
        inSelectElement = true;
    });
    $tabContent.on('blur', '.collapse', function() {
        inSelectElement = false;
    });
});
