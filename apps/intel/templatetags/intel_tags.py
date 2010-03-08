from django import template
from django.http import HttpRequest
from django.template import RequestContext


register = template.Library()

@register.simple_tag
# def tabs(current_page, search_term):
# 
#     def is_current(tab_name):
#         if tab_name == current_page:
#             return "active"
#         else:
#             return ""
#         
#     tabs = { "all"    : "All Pregnant Mothers", "risk"   : "High Risk For Follow Up", "chart"  : "Program Trends" }
#             
#     t = '<ul id="tabs">'
#     for i in tabs:
#         t+= '<li class="app-intel-%s %s"><a href="/intel/%s"><span>%s</a></li>' % (i, is_current(i), i, tabs[i])
#     
#     t += '''
#         <li>
#             <form action="/intel/all" method="get" style="padding-left: 15px">
#                 <input type="text" size="20" name="search" value="%s"/>&nbsp;
#                 <input type="submit" value="Search by Mother Name"/>
#             </form>
#         </li>
#         </ul>''' % search_term
# 
#     return t

def tabs(current_page, search_term):

    def is_current(tab_name):
        if tab_name == current_page:
            return "active"
        else:
            return ""

    tabs = { "all" : 
                {
                    "text" : "All Pregnant Mothers",
                    "color": "#ff6100"
                },
                
             "risk":  
                {
                    "text" : "High Risk For Follow Up",
                    "color": "#82c700"
                },
              "chart": 
                {
                    "text" : "Program Trends",
                    "color": "#0099ff"
                }
            }

    t = '<div class="buttons">'
    for i in tabs:
        bgcolor = (tabs[i]["color"] if i == current_page else "white")
        t+= '<a href="/intel/%s" style="background-color: %s">%s</a>\n' % (i, bgcolor, tabs[i]["text"])

    # icon from http://pixel-mixer.com/ - free for use but link required. We might want to have our own instead.
    t += '<a href="/intel/all" style="position: absolute; right: 0;"><img src="/static/intel/img/home.png" /></a><!-- icon by http://pixel-mixer.com/ -->'
    
    # t += '''
    #     <li>
    #         <form action="/intel/all" method="get" style="padding-left: 15px">
    #             <input type="text" size="20" name="search" value="%s"/>&nbsp;
    #             <input type="submit" value="Search by Mother Name"/>
    #         </form>
    #     </li>
    #     </ul>''' % search_term

    t += "</div>"
    
    t += '<script type="text/javascript">$("#header").css("border-bottom-color", "%s");</script>' % tabs[current_page]["color"]

    return t
