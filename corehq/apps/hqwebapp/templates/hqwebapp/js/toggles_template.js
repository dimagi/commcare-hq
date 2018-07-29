{% load hq_shared_tags %}
hqDefine('hqwebapp/js/toggles_template', function () {
    return {
        toggles: {{ toggles_dict|JSON }},
        previews: {{ previews_dict|JSON }}
    };
});
