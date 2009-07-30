from lxml import etree
import sys

if len(sys.argv)<3:
    print "usage: prettify input_xml_file output_xml_file"
    sys.exit(1)

f = open(sys.argv[1], 'r')
tree = etree.parse(f)
f.close()

f = open(sys.argv[2],'w')
root = tree.getroot()
f.write(etree.tostring(root, pretty_print=True))
f.close()

print "success!"

