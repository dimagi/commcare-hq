from django import template
import urllib

register = template.Library()

@register.tag
def urlencode(parser, token):
    tokens = list(reversed(token.split_contents()))
    tag_name = tokens.pop()
    try:
        path_var = tokens.pop()
        params_var = tokens.pop()
    except:
        raise template.TemplateSyntaxError, "%r requires at least 2 parameters" % tag_name
    params = {}
    delete = set()
    while(tokens):
        cmd = tokens.pop()
        if cmd == "with":
            try:
                key = tokens.pop()
                assert(tokens.pop() == "as")
                value = tokens.pop()
            except:
                raise template.TemplateSyntaxError, "%r tag has incomplete 'with...as'" % tag_name
            params[key] = value
        elif cmd == "without":
            try:
                delete.add(tokens.pop())
            except:
                raise template.TemplateSyntaxError, "%r tag has incomplete 'without'" % tag_name
        else:
            raise template.TemplateSyntaxError, "%r tag found '%s'; expected 'with...as' or 'without'" % (tag_name, cmd)

    return URLEncodeNode(path_var, params_var, params, delete)

class URLEncodeNode(template.Node):
    def __init__(self, path_var,  params_var, extra_params, delete_params):
        self.path_var = template.Variable(path_var)
        self.params_var = template.Variable(params_var)
        self.extra_params = extra_params
        self.delete_params = delete_params

    def render(self, context):
        path = self.path_var.resolve(context)
        params = {}
        for key,val in self.params_var.resolve(context).lists():
            params[key] = val

        for key,val in self.extra_params.items():
            key = template.Variable(key).resolve(context)
            val = template.Variable(val).resolve(context)
            params[key] = val
        for key in self.delete_params:
            key = template.Variable(key).resolve(context)
            params.pop(key, None)

        # clean up
        for key in params:
            if isinstance(params[key], unicode):
                params[key] = params[key].encode('utf-8')
        return "%s?%s" % (path, urllib.urlencode(params, True)) if params else path