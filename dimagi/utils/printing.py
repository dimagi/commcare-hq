import sys, traceback

"""Utilities for printing things"""

def print_exc():
    """Print the latest exception on the stack"""
    print_exc_message()
    print_exc_stack()
    
def print_exc_message():
    """Print the message of the latest exception on the stack"""
    print sys.exc_info()[0]

def print_exc_stack():
    """Print the stack of the latest exception on the stack"""
    print "\n".join(traceback.format_tb(sys.exc_info()[2]))
    
def print_list(l, sep=", "):
    """Print a list"""
    print "%s item list" % len(l)
    print sep.join([str(i) for i in l])
        