from django import forms
from django.utils.safestring import mark_safe
import json

class AutocompleteTextarea(forms.Textarea):
    """
    Textarea with auto-complete.  Requires Twitter Bootstrap typeahead JS
    plugin to be available.
    
    """

    class Media:
        js = ('hqwebapp/js/jquery.multi_typeahead.js',)

    def render(self, name, value, attrs=None):
        if hasattr(self, 'choices') and self.choices:
            output = mark_safe("""
<script>
$(function() {
    $("#%s").multiTypeahead({
        source: %s
    });
});
</script>\n""" % (attrs['id'], json.dumps(self.choices)))

        else:
            output = mark_safe("")

        output += super(AutocompleteTextarea, self).render(name, value,
                                                           attrs=attrs)
        return output
