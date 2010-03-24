from django import template
from django.http import HttpRequest
from django.template import RequestContext


register = template.Library()

@register.simple_tag
def tabs(current_page):

    tabs = { "all" : 
                {
                    "tooltip" : "All Pregnant Mothers", # we don't have tooltips, but maybe someday
                    "text" : "Pregnant Mothers",
                    "color": "#ff6100",
                    "icon" : "/static/intel/img/icons/preg-icon.png"
                },
                
             "risk":  
                {
                    "tootlip" : "High Risk For Follow Up",
                    "text" : "High Risk",
                    "color": "#82c700",
                    "icon" : "/static/intel/img/icons/risk-icon.png"
                },
              "chart": 
                {
                    "tooltip" : "Program Trends",
                    "text" : "Program Trends",
                    "color": "#0099ff",
                    "icon" : "/static/intel/img/icons/trends-icon.png"
                }
            }

    t = '<div class="buttons">'
    
    for i in tabs:
        # bgcolor = (tabs[i]["color"] if i == current_page or current_page == "home" else "white")
        #t+= '<a href="/intel/%s" style="background-color: %s">%s</a>\n' % (i, bgcolor, tabs[i]["text"])
        but = '<a href="/intel/%s"><img class="left" src="%s"/><span style="vertical-align:top">%s</span></a>' % (i, tabs[i]["icon"], tabs[i]["text"])
        if i == current_page or current_page == "home":
            t += but 
            
        #but = '<span style="border: 5px solid %s">%s</span>' % (tabs[i]["color"], but)
        

    if current_page != "home":
        # icon from http://pixel-mixer.com/ - free for use but link required. We might want to get our own instead.
        #t += '<a href="/intel/" style="position: absolute; right: 0;"><img src="/static/intel/img/home.png" /></a><!-- icon by http://pixel-mixer.com/ -->'
        t += '<a href="/intel/" style="position: absolute; right: 0; width: 90px"><img src="/static/intel/img/icons/home-icon.png" /></a>'
    t += "</div>"
    
    if tabs.has_key(current_page): 
        t += '<script type="text/javascript">$("#header").css("border-bottom-color", "%s");</script>' % tabs[current_page]["color"]

    return t
