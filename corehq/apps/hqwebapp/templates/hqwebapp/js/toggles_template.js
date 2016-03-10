{% load hq_shared_tags %}
hqDefine('#toggles', function () {
    return {
        toggles: {{ toggles_dict|JSON }},
        previews: {{ previews_dict|JSON }}
    };
});
