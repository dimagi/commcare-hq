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
        # to show only the currnent page icon add: if i == current_page or current_page == "home"
        # t += '<a href="/intel/%s" style="%s"><img class="left" src="%s"/><span style="vertical-align:top">%s</span></a>' % (i, style, tabs[i]["icon"], tabs[i]["text"])

        style = "background: url('%s') no-repeat 7px 7px;" % tabs[i]["icon"]
        if i == current_page: style += " border: solid 4px #c3d9ff;"

        t += '<a href="/intel/%s" style="%s"><span style="position:relative; top:25px; left:0px;">%s</span></a>' % \
            (i, style, tabs[i]["text"])

    if current_page != "home":
        t += '<a href="/intel/" style="float: right; width: 90px"><img src="/static/intel/img/icons/home-icon.png" /></a>'
    t += "</div>"
    
    return t


def _doctor_tabs():
    return { "all" : 
                {
                    "text" : "Pregnant Mothers",
                    "icon" : "/static/intel/img/icons/preg-icon.png"
                },
             "risk":  
                {
                    "text" : "High Risk",
                    "icon" : "/static/intel/img/icons/risk-icon.png"
                },
              "chart": 
                {
                    "text" : "Program Trends",
                    "icon" : "/static/intel/img/icons/trends-icon.png"
                }
            }

def _hq_tabs():
    return { "hq_risk":  
                {
                    "text" : "High Risk",
                    "icon" : "/static/intel/img/icons/risk-icon.png"
                },
              "hq_chart": 
                {
                    "text" : "Program Trends",
                    "icon" : "/static/intel/img/icons/trends-icon.png"
                }
            }
    