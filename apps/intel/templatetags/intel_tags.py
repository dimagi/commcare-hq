from django import template

register = template.Library()

@register.simple_tag
def tabs(current_page):

    def active_flag(tab_name):
        if tab_name == current_page:
            return "active"
        else:
            return ""
        
    tabs = { "all"    : "All Pregnant Mothers", "risk"   : "High Risk For Follow Up", "chart"  : "Program Trends" }
            
    t = '<ul id="tabs">'
    for i in tabs:
        t+= '<li class="app-intel-%s %s"><a href="/intel/%s"><span>%s</a></li>' % (i, active_flag(i), i, tabs[i])
    
    t+='</ul>'
    return t