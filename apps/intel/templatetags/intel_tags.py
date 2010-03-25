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
        style = "border: solid 4px #c3d9ff" if i == current_page else ""
        but = '<a href="/intel/%s" style="%s"><img class="left" src="%s"/><span style="vertical-align:top">%s</span></a>' % (i, style, tabs[i]["icon"], tabs[i]["text"])

        # uncomment to show only the currnent page icon 
        # if i == current_page or current_page == "home":
        t+=but

    if current_page != "home":
        t += '<a href="/intel/" style="float: right; width: 90px"><img src="/static/intel/img/icons/home-icon.png" /></a>'
    t += "</div>"
    
    # if tabs.has_key(current_page): 
        # t += '<script type="text/javascript">$("#header").css("border-bottom-color", "%s");</script>' % tabs[current_page]["color"]

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
    