#!/usr/bin/env python
#
# insert_loadfile.py - Replace load_file calls with the actual file

import re
from sys import argv, stderr
from base64 import encodestring


if len(argv) != 3:
    print >> stderr, 'usage: %s INPUTFILE OUTPUT' % argv[0]

pat = re.compile(r'''=\s*load_file\s*\( *['"]([^'"]+)['"] *\)''')

f = open(argv[1])

out = ''

for l in f:
    m = pat.search(l)
    if m:
        i = encodestring(open(m.group(1)).read())
        l = pat.sub(r"""= b64decode('''\n%s''')""" % i, l)

    out += l

open(argv[2], 'w').write(out)
