#!/usr/bin/env python
##
# test_vimhelper.py
###
"""test_vimhelper.py

"""

__version__ = "0.1"
__author__ = "Danny O'Brien <http://www.spesh.com/danny/>"
__copyright__ = "Copyright Danny O'Brien"
__contributors__ = None
__license__ = "GPL v3"


import doctest
import unittest
import vimhelper
import os
import tempfile
import time

def list_compare(vb, l):
    if len(vb) != len(l):
        print len(vb), "not same length as ", len(l)
        print repr(vb), l
        return False
    for i in range(0,len(vb)-1):
        if vb[i] != l[i]:
            print vb[i], l[i], "not the same @",i
            return False
    return True


class TestVimBuffer(unittest.TestCase):
    def setUp(self):
        tf = tempfile.NamedTemporaryFile('w', delete=False)
        self.tempname = tf.name
        print >> tf, "0\n1\n2\n3\n4\n5\n6"
        tf.close()
        os.system("vim -g --servername TESTER %s" % tf.name)
        time.sleep(0.4)

    def test_arrayishness_of_vimbuffer(self):
        v = vimhelper.VimBuffer("TESTER", self.tempname)
        self.assertEquals(v[0], '0')
        self.assertEquals(v[1], '1')
        self.assertEquals(v[2], '2')
        self.assertEquals(v[3], '3')
        c = ['0','1','2','3','4','5','6']
        self.assert_(list_compare(v,c))
        c[1] = 'not 1'
        v[1] = 'not 1'
        self.assert_(list_compare(v,c))
        c[1:1] = ['expand','me']
        v[1:1] = ['expand','me']
        self.assert_(list_compare(v,c))

    def tearDown(self):
        os.system('vim -g --servername TESTER --remote-send \'<Esc>:q!<CR>\'')
        os.unlink(self.tempname)

if __name__ == '__main__':
    import __main__
    try:
        suite = doctest.DocTestSuite()
    except ValueError:
        suite = unittest.TestLoader().loadTestsFromModule(__main__)
    else:
        suite.addTest(unittest.TestLoader().loadTestsFromModule(__main__))
    unittest.TextTestRunner(verbosity=1).run(suite)

