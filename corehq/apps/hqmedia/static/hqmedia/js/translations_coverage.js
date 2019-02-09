hqDefine("hqmedia/js/translations_coverage", function () {
    $(function () {
        var $form = $("#hq-content").find(".form-horizontal"),
            showResult = function (content, cls) {
                $("#results").removeClass()
                             .addClass("alert alert-" + cls)
                             .html(content);
            };

        $form.find("select").select2();

        $form.submit(function () {
            var data = {
                langs: $form.find("select[name='langs']").val(),
                media_types: $form.find("select[name='media_types']").val(),
            };
            if (!data.langs.length) {
                showResult("Please select a language.", "danger");
                return false;
            }
            if (!data.media_types.length) {
                showResult("Please select a media type.", "danger");
                return false;
            }

            var $button = $form.find("submit");
            $button.disableButton();
            $.ajax({
                method: 'GET',
                url: hqImport("hqwebapp/js/initial_page_data").reverse("check_translations_coverage"),
                data: data,
                success: function (data) {
                    $button.enableButton();
                    if (data.error) {
                        showResult(data.error, "danger");
                    } else {
                        showResult(data.langs, "success");
                    }
                },
                error: function () {
                    $button.enableButton();
                    showResult(gettext("There was an error checking your app. "
                        + "Please try again or report an issue if the problem persists."), "danger");
                },
            });

            return false;
        });
    });
});
