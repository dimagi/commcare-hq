
MISSING_DEPENDECY = \
"""Aw shucks, someone forgot to install the google chart library 
on this machine and the report needs it. To get it, run 
easy_install pygooglechart.  Until you do that this won't work.
"""

def get_punchcard_url(data, width=950, height=300):
    '''
    Gets a github style punchcard chart. 
    
    Hat tip: http://github.com/dustin/bindir/blob/master/gitaggregates.py
    '''
    if not data: return ""
    try:
        from pygooglechart import ScatterChart
    except ImportError:
        raise Exception(MISSING_DEPENDECY)

    chart = ScatterChart(width, height, x_range=(-1, 24), y_range=(-1, 7))

    chart.add_data([(h % 24) for h in range(24 * 8)])

    d=[]
    for i in range(8):
        d.extend([i] * 24)
    chart.add_data(d)

    day_names = "Sun Mon Tue Wed Thu Fri Sat".split(" ")
    days = (0, 6, 5, 4, 3, 2, 1)

    sizes=[]
    for d in days:
        sizes.extend([data["%d %02d" % (d, h)] for h in range(24)])
    sizes.extend([0] * 24)
    chart.add_data(sizes)

    chart.set_axis_labels('x', [''] + [str(h) for h  in range(24)] + [''])
    chart.set_axis_labels('y', [''] + [day_names[n] for n in days] + [''])

    chart.add_marker(1, 1.0, 'o', '333333', 25)
    return chart.get_url() + '&chds=-1,24,-1,7,0,20'