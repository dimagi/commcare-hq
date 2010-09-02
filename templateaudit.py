from django.template import VariableNode, Node, TextNode
from django.template.loader import get_template
from django.template.loader_tags import ExtendsNode, BlockNode
from django.template.defaulttags import WithNode


'''
Method loads template and iterates through the template's NodeList to 
check for auditable types. Currently does not consider the request
type.

@param template_name: string name of template to load
@param auditable: list of objects to audit
@return: dictionary of occurrences of object...
for debugging, right now string representation 
'''

def audit(request, template_name, context, auditable=None):
    # Initialize template and nodes
    template = get_template(template_name)
    nodeList = template.nodelist    
    
    temp = []
    result = []
    temp = expandWithNodes(expandBlockNodes(expandExtendNodes(nodeList)))
    
    for node in temp:        
        if isinstance(node, VariableNode):
            result.append(node)    
    
    #print request.path
    #print request.user
    #print result[0].render(context)
    
        
    nodes = []
    for res in result:
        iter = res.__iter__()
        try:            
            while 1: 
                node = iter.next()
                print node                     
        except Exception, e:            
            pass
        
    res2 = walkTemplate(template)
    for res in res2:
        if isinstance(res, VariableNode):
            print res
            print str(res) + " :: " + str(res.render(context))
            #print unicode(res.render(context))
            pass
    
    return result


def walkTemplate(template):
    nodeList = template.nodelist    
    result = []
    result += expandNodes(nodeList)
    
    return result

def expandNodes(nodeList):
    result = []
    
    
    while len(nodeList) > 0:
        node = nodeList.pop(0)
        if isinstance(node, ExtendsNode):
            nodeList += expandExtendNodes(node.nodelist)
            parent_template = node.get_parent(node.parent_name)
            nodeList += walkTemplate(parent_template)
        elif isinstance(node, BlockNode):
            nodeList += expandBlockNodes(node.nodelist)
        elif isinstance(node, WithNode):
            nodeList += expandWithNodes(node.nodelist)
        else:
            result += node
    return result



def expandExtendNodes(nodeList):
    result = []
    for node in nodeList:    
        if isinstance(node, ExtendsNode):
            result += expandExtendNodes(node.nodelist)
            print node.get_parent(node.parent_name)
        else:            
            result += node    
    return result

def expandBlockNodes(nodeList):
    result = []
    for node in nodeList:
        if isinstance(node, BlockNode):
            result += expandBlockNodes(node.nodelist)
        else:
            result += node
    return result 

def expandWithNodes(nodeList):
    result = []
    for node in nodeList:
        if isinstance(node, WithNode):
            result += expandWithNodes(node.nodelist)
        else:
            result += node    
    return result 

def expandForNodes(nodeList):
    result = []
    for node in nodeList.nodelist_loop:        
        result += node
    return result