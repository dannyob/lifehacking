#!/usr/bin/env python
##
# vimhelper.py
###
"""vimhelper.py

Some useful vim classes
"""

__version__ = "0.1"
__author__ = "Danny O'Brien <http://www.spesh.com/danny/>"
__copyright__ = "Copyright Danny O'Brien"
__contributors__ = None
__license__ = "GPL"
__url__ = "$HeadURL$"
__cvsversion__ = "$Revision$"
__date__ = "$Date$"

import logging
rootLogger = logging.getLogger('')
rootLogger.setLevel(logging.DEBUG)

from subprocess import Popen, PIPE
class _VimCaller:
    def __init__(self, send, name):
        self.__send = send
        self.__name = name
    def __call__(self, *args):
        return self.__send(self.__name, args)

def vimrepr(o):
    r""" fix strings for Vim 
    >>> i = 'hello'
    >>> print vimrepr(i)
    "hello"
    """
    z = repr(o)
    if z[0] == "'" and z[-1] == "'":
        return '"'+z[1:-1].replace('"',r'\"')+'"'
    else:
        return z

class VimProxy:
    def __init__(self, servername):
        self.servername = servername
    
    def do(self,command, remoteform='remote-expr'):
        r = '--'+remoteform
        if r == "--remote-expr":
            logging.debug("calling function %s" % command)
        if r == "--remote-send":
            logging.debug("sending keys %s" % command)
        p=Popen(['vim','--servername', self.servername, r, command], stdout=PIPE, stderr=file("/dev/null"))
        return (p.communicate()[0]).rstrip('\n')

    def sendkeys(self, keys):
        return self.do(keys, remoteform='remote-send')

    def __getattr__(self, name):
        return _VimCaller(self.__sender__, name)

    def __sender__(self, function, args):
        m = [vimrepr(i) for i in args]
        command="%s(%s)" % (function, ','.join(m))
        return self.do(command)

class VimBufferNotFound(Exception):
    pass

class VimBuffer():
    def __repr__(self):
        s = 'VimBuffer(%s,%s): [' % (self.server, self.buffer)
        if self.__len__()==0:
            return s+']'
        for i in self:
            s += repr(i)+", "
        return s[0:-2]+"]"

    def __init__(self, server, buffername):
        self.server = server
        self.buffer = buffername
        self.vimp = VimProxy(server)
        try:
            self.bufnum = int(self.vimp.bufexists(buffername))
        except ValueError:
            raise VimBufferNotFound("Could not find " + self.buffer)
        
    def __getitem__(self, n):
        if isinstance(n, slice):
            return self.vimp.getline(n.start+1, n.stop+1).split('\n')
        if n<0:
            n = len(self)+n
        l=self.vimp.getline(n+1)
        if not l:
            if n > len(self):
                raise IndexError
        return l

    def replace(self, start, stop, value):
        # FIXME right now this assumes that autoindent is ON
        # (the '!' in 'change!' means 'toggle autoindent'
        realstart = str(start +1)
        realstop = str(stop +1)
        if stop >= 2147483646:
            realstop = "$"
        self.vimp.sendkeys('<Esc>:%s,%s change!\n' % (realstart,realstop) )
        for l in value:
            self.vimp.sendkeys(l+'\n')
        self.vimp.sendkeys('.\n')
        
    def __setitem__(self, n, v):
        if isinstance(n, slice):
            self.replace(n.start, n.stop, v)
            return
        m=self.vimp.setline(n+1, v)
        if not m:
            raise IndexError

    def __len__(self):
        return int(self.vimp.line('$'))

    def __iter__(self):
        z = self[0:-1]
        for l in z:
            yield l
 
def main(args):
    """ Put your main command line runner here """
    pass

import sys, getopt
class Main():
    """ Encapsulates option handling. Subclass to add new options,
        add 'handle_x' method for an -x option,
        add 'handle_xlong' method for an --xlong option
        help (-h, --help) should be automatically created from module
        docstring and handler docstrings.
        test (-t, --test) will run all docstring and unittests it finds
        """
    class Usage(Exception):
        def __init__(self, msg):
            self.msg = msg
    def __init__(self):
        handlers  = [i[7:] for i in dir(self) if i.startswith('handle_') ]
        self.shortopts = ''.join([i for i in handlers if len(i) == 1])
        self.longopts = [i for i in handlers if (len(i) > 1)]
    def handler(self,option):
        i = 'handle_%s' % option.lstrip('-')
        if hasattr(self, i):
           return getattr(self, i)
    def default_main(self, args):
        print sys.argv[0]," called with ", args
    def handle_help(self, v):
        """ Shows this message """
        print sys.modules.get(__name__).__doc__
        descriptions = {}
        for i in list(self.shortopts) + self.longopts:
            d=self.handler(i).__doc__
            if d in descriptions:
               descriptions[d].append(i)
            else:
               descriptions[d] = [i]
        for d, o in descriptions.iteritems():
            for i in o:
                if len(i) == 1:
                    print '-%s' % i,
                else:
                    print '--%s' % i,
            print 
            print d
        sys.exit(0)
    handle_h=handle_help

    def handle_test(self, v):
        """ Runs test suite for file """
        import doctest
        import unittest
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules.get(__name__))
        suite.addTest(doctest.DocTestSuite())
        runner = unittest.TextTestRunner()
        runner.run(suite)
        sys.exit(0)
    handle_t=handle_test

    def handle_debug(self, v):
        """ Turns on debug logging """
        rootLogger = logging.getLogger('')
        rootLogger.setLevel(logging.DEBUG)
    handle_d=handle_debug

    def run(self, main= None, argv=None):
        """ Execute main function, having stripped out options and called the
        responsible handler functions within the class. Main defaults to
        listing the remaining arguments.
        """
        if not callable(main):
            main = self.default_main
        if argv is None:
            argv = sys.argv
        try:
            try:
                opts, args = getopt.getopt(argv[1:], self.shortopts, self.longopts)
            except getopt.error, msg:
                raise self.Usage(msg)
            for o, a in opts:
                (self.handler(o))(a)
            return main(args) 
        except self.Usage, err:
            print >>sys.stderr, err.msg
            self.handle_help(None)
            return 2

if __name__ == "__main__":
    sys.exit(Main().run(main) or 0)

