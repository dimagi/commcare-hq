from django import template
from django.http import HttpRequest
from django.template import RequestContext


register = template.Library()

@register.simple_tag


def tabs(current_page, hq_mode=False):

    if hq_mode:
        tabs = _hq_tabs()
    else:
        tabs = _doctor_tabs()
    
    t = '<div class="buttons">'
    
    for i in tabs:
        # bgcolor = (tabs[i]["color"] if i == current_page or current_page == "home" else "white")
        #t+= '<a href="/intel/%s" style="background-color: %s">%s</a>\n' % (i, bgcolor, tabs[i]["text"])
        but = '<a href="/intel/%s"><img class="left" src="%s"/><span style="vertical-align:top">%s</span></a>' % (i, tabs[i]["icon"], tabs[i]["text"])
        if i == current_page or current_page == "home":
            t += but 
        

    if current_page != "home":
        t += '<a href="/intel/" style="float: right; width: 90px"><img src="/static/intel/img/icons/home-icon.png" /></a>'
    t += "</div>"
    
    # if tabs.has_key(current_page): 
    #     t += '<script type="text/javascript">$("#header").css("border-bottom-color", "%s");</script>' % tabs[current_page]["color"]

    return t



def _doctor_tabs():
    return { "all" : 
                {
                    "text" : "Pregnant Mothers",
                    # "color": "#ff6100",
                    "icon" : "/static/intel/img/icons/preg-icon.png"
                },

             "risk":  
                {
                    "text" : "High Risk",
                    # "color": "#82c700",
                    "icon" : "/static/intel/img/icons/risk-icon.png"
                },
              "chart": 
                {
                    "text" : "Program Trends",
                    # "color": "#0099ff",
                    "icon" : "/static/intel/img/icons/trends-icon.png"
                }
            }

def _hq_tabs():
    return { "hq_risk":  
                {
                    "text" : "High Risk",
                    # "color": "#82c700",
                    "icon" : "/static/intel/img/icons/risk-icon.png"
                },
              "hq_chart": 
                {
                    "text" : "Program Trends",
                    # "color": "#0099ff",
                    "icon" : "/static/intel/img/icons/trends-icon.png"
                }
            }
    