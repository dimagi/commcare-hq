/*global $:false, window:false */
(function () {
    var alertHtml = function (message, alert_class) {
        return (
            "<div class='alert " + (alert_class || 'alert-info') + "'>" +
            "<button type='button' class='close' data-dismiss='alert'>&times;</button>" +
            message +
            "</div>"
        );
    };

    $.fn.inlineFormplayer = function (options) {
        var $target = $($(this).get(0));
        options.onerror = options.onerror || function () {};
        options.onload = options.onload || function () {};
        options.lang = options.lang || 'en';

        $.ajax({
            url: options.formUrl,
            dataType: "json",
            success: function (data) {
                var loading = $('.hq-loading');
                var onLoading = function () {
                    loading.show();
                };
                var onLoadingComplete = function () {
                    loading.hide();
                };
                $target.show();

                data.session_data = $.extend(data.session_data, options.sessionData);

                data = $.extend(data, {
                    onsubmit: function (xml) {
                        $target.html(alertHtml('Form successfully submitted!', 'alert-success'));
                        options.onsubmit();
                    },
                    onerror: function (resp) {
                        $target.html(alertHtml(
                            resp.human_readable_message || resp.message || 'An unexpected error occurred!',
                            'alert-danger'
                        ));
                    },
                    onload: function (adapter, resp) {
                        options.onload();
                    },
                });
                data.onLoading = onLoading;
                data.onLoadingComplete = onLoadingComplete;
                data.uses_sql_backend = options.uses_sql_backend;
                data.post_url = options.submitUrl;
                data.domain = options.domain;
                data.username = options.username;
                data.restoreAs = options.restoreAs;
                var sess = new WebFormSession(data);
                sess.load($target, options.lang);
            },
        });
    };

    $("body").on('click', '.formplayer-link', function () {
        var getFormUrl = hqImport('cloudcare/js/util').getFormUrl;
        var getSubmitUrl = hqImport('cloudcare/js/util').getSubmitUrl;
        var $this = $(this),
            $target = $($this.data('target')),
            appId = $this.data('app-id'),
            moduleId = $this.data('module-id'),
            formId = $this.data('form-id'),
            instanceId = $this.data('instance-id') || null,
            formUrl = getFormUrl($this.data('form-url-root'), appId, moduleId, formId, instanceId),
            submitUrl = getSubmitUrl($this.data('submit-url-root'), appId),
            sessionData = $this.data('session-data') || {};

        $this.data('original-html', $this.data('original-html') || $this.html());

        if ($this.data('state') === 'disabled') {
            return false;
        }

        // can't use individual off('click') because of event delegation
        if (!$this.data('state') || ($this.data('state') === 'closed')) {
            $this.data('state', 'disabled');
            $target.inlineFormplayer({
                formUrl: formUrl,
                submitUrl: submitUrl,
                sessionData: sessionData,
                onsubmit: function () {
                    $this.html($this.data('original-html'));
                    $this.click();
                    $this.data('state', 'closed');
                    window.location.reload();
                },
                onload: function () {
                    $this.html("<i class='icon-remove'></i> Cancel")
                        .data('state', 'open');
                },
            });
        } else {
            $this.html($this.data('original-html'));
            $target.hide().html("");
            $this.data('state', 'closed');
        }

        return false;
    });
}());
