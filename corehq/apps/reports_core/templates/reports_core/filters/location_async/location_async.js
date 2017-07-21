  {% load reports_core_tags %}
  {% load hq_shared_tags %}

  $.getScript("{% static 'locations/js/location_drilldown.async.js' %}", function() {

      var loc_url = '{{ context_.loc_url }}';
      var locs = {{ context_.locations|JSON }};
      var selected = '{{ context_.loc_id|default_if_none:"" }}';
      var hierarchy = {{ context_.hierarchy|JSON }};

      var show_location_filter = {% if not context_.loc_id %}'n'{% else %}'y'{% endif%};
      var model = new LocationSelectViewModel({
        "hierarchy": hierarchy,
        "auto_drill": false,
        "loc_url": loc_url,
        "max_drill_depth": '{{ context_.max_drilldown_levels }}'
      });
      $('#group_{{ context_.input_name }}').koApplyBindings(model);
      model.load(locs, selected);

  });
