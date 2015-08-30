#!/usr/bin/env python
##
# todo.py
###
"""todo.py

"""
import datetime
import time
import random
import re 
import subprocess
import sys, getopt
import os, os.path

import vimhelper
import dateutil.rrule


__version__ = "0.2"
__author__ = "Danny O'Brien <http://www.spesh.com/danny/>"
__copyright__ = "Copyright Danny O'Brien"
__contributors__ = None
__license__ = "GPL v3 or above"
__url__ = "$HeadURL$"
__cvsversion__ = "$Revision$"
__date__ = "$Date$"


 
def timestamp():
    # there's a race condition here at 23:59:59 on a timezone change day!
    return time.strftime('%Y-%m-%dT%H:%M-%%02d00') % (time.timezone/(3600))

class Tag(str):
    """ A string with helper functions to grok tags 
    >>> i = Tag('@POOT(yip)')
    >>> print i.is_context()
    True
    >>> print i.is_project()
    False
    >>> print i.argument()
    ['yip']
    >>> print i
    @POOT(yip)
    >>> print i.name()
    @POOT
    """
    tag_regexp = r'(\s|\A)(?P<all>(?P<name>[@#$][A-Z_0-9]*)(\((?P<arg>.*?)\))?)'
    tag_regexp_name_group  = 1
    tag_regexp_arg_group = 4

    @staticmethod
    def current_tag():
        return Tag('@CURRENT')

    @staticmethod
    def ignore_tag(t=None):
        """ Create the tag which indicates when this should be next paid attention to"""
        if t == None:
            return Tag('@IGNOREUNTIL') # generic tag
        return Tag("@IGNOREUNTIL(%s)" % (t.isoformat()[:16]))

    @staticmethod
    def urgent_tag():
        return Tag('@URGENT')

    @staticmethod
    def repeat_tag(arg=None):
        return Tag('@REPEAT(%s)' % arg)
    

    @staticmethod
    def extract_tags(s):
        """ pull out tags from a string 
        >>> m = Tag.extract_tags('por bun wolly @FOO #BAR @BING @BLAH(54 54) @BOO(12 13)')
        >>> print m
        ['@FOO', '#BAR', '@BING', '@BLAH(54 54)', '@BOO(12 13)']
        >>> m[-1].argument()
        ['12 13']
        """
        l = []
        for i in re.finditer(Tag.tag_regexp, s):
            t = Tag(i.group('all'))
            l.append(t)
        return l

    def __init__(self,s):
        self.parse_argument()

    def ignore_from_repeat(self, now):
        r""" Creates an Ignore tag that makes sure this todo is repeated in the future.
        The time until the ignore expires is taken from the repeat tag argument -- a
        repeat tag with days=7 will return a ignore tag with a date seven days in the future.
        >>> i = Tag.repeat_tag('WEEKLY')
        >>> print i.ignore_from_repeat(datetime.datetime(year=1990, day=1, month=1))
        @IGNOREUNTIL(1990-01-08T00:00)
        >>> i = Tag.repeat_tag('YEARLY')
        >>> print i.ignore_from_repeat(datetime.datetime(year=1990, day=1, month=1))
        @IGNOREUNTIL(1991-01-01T00:00)
        >>> i = Tag.repeat_tag('HOURLY,interval=2')
        >>> print i.ignore_from_repeat(datetime.datetime(year=1990, day=1, month=1))
        @IGNOREUNTIL(1990-01-01T02:00)
        """
        repeat_args = [ i.split('=') for i in self.argument()[1:]]
        repeat_dict = dict([ (i, eval(j, {}, {}) ) for (i,j) in repeat_args ])
        repeat_dict['dtstart'] = now
        repeat_rule = dateutil.rrule.rrule(eval(self.argument()[0],
                                                dateutil.rrule.__dict__, {}),
                                           **repeat_dict)
        return Tag.ignore_tag(repeat_rule.after(now))
     
    def parse_argument(self):
        if '(' in self:
            m = re.match(Tag.tag_regexp, self)
            if not m:
                return None
            self.args = m.group('arg').split(',')
            return self.args

    def is_project(self):
        return self[0] == '#'

    def is_context(self):
        return self[0] == '@'

    def argument(self):
        try:
            return self.args
        except:
            return self.parse_argument()

    def name(self):
        if '(' in self:
            return str(self[:self.find('(')])
        else:
            return str(self)

    def same_name_as(self, t):
        r""" 
        >>> m = Tag('@FRED(3)')
        >>> n = Tag('@FRED(45)')
        >>> o = Tag('@FRED')
        >>> print m.same_name_as(n)
        True
        >>> print m.same_name_as(o)
        True
        >>> print m.same_name_as(m)
        True
        >>> print o.same_name_as(m)
        True
        """
        return self.name() == t.name()

    def is_ignore(self):
        r""" returns if this a ignore tag 
        >>> i = Tag('@IGNOREUNTIL(2004-05-02)')
        >>> print str(i)
        @IGNOREUNTIL(2004-05-02)
        >>> print i.is_ignore()
        True
        """
        return self.name() == '@IGNOREUNTIL'

    def is_repeat(self):
        r""" returns if this is a repeat tag
        >>> i= Tag('@REPEAT(day=7)')
        >>> print str(i)
        @REPEAT(day=7)
        >>> print i.is_repeat()
        True
        >>> i= Tag('@REPEATME(day=7)')
        >>> print i.is_repeat()
        False
        """
        return self.name() == '@REPEAT'

    def find_in(self, s):
        r""" find a single tag and return its position in a string.
        Returns None or (start, end) tuple 
        >>> print Tag('@BLAH(54 54)').find_in('por bun wolly @FOO #BAR @BING @BLAH(54 54)')
        (30, 42)
        >>> print Tag('@BLAH').find_in('por bun wolly @FOO #BAR @BING @BLAH(54 54)')
        (30, 42)
        """
        m = [i for i in re.finditer(Tag.tag_regexp, s) if i.group('name') == str(self.name()) ]
        if len(m) == 0:
            return None
        if len(m) > 1:
            raise TodoError('More than one %s tag in string %s' % (str(self), s))
        return (m[0].start('all'), m[0].end('all'))

class ContextHandler():
    work_wifi = ['gnu']         # Yours
    home_wifi = ['spesh.com/wifi', 'Maze']   # will vary
    auto_tags = { '@HOME' : lambda s: s.athome(),
            '@WORK' : lambda s: s.atwork(),
            '@MONDAY' : lambda s: (s.dow() == 1 ),
            '@TUESDAY' : lambda s: (s.dow() == 2 ),
            '@WEDNESDAY' : lambda s: (s.dow() == 3 ),
            '@THURSDAY' : lambda s: (s.dow() == 4 ),
            '@FRIDAY' : lambda s: (s.dow() == 5 ),
            '@SATURDAY' : lambda s: (s.dow() == 6 ),
            '@SUNDAY' : lambda s: (s.dow() == 7 ),
            '@WEEKEND' : lambda s: (s.dow() == 6 or s.dow() == 7),
            '@MORNING' : lambda s: (s.hour() <= 12 and s.hour() >= 8),
            '@AFTERNOON' : lambda s: (s.hour() >= 12 and s.hour() <= 17),
            '@EVENING' : lambda s: (s.hour() >=17 and s.hour() <= 22),
            '@UKTIME' : lambda s: (s.hour() >= 0 and s.hour() <= 11),
            '@EASTCOASTTIME' : lambda s: (s.hour() >= 6 and s.hour() <= 15),
            '@LUNCH' : lambda s: (s.hour() >= 12 and s.hour() <= 13 ),
            '@WORKDAY' : lambda s: (s.hour() >= 9 and s.hour() <= 18 and s.weekday()), 
            '@DAILY': lambda s: True,
            '@URGENT' : lambda s: True }

    def wifi(self):
        # Linux only I'm afraid
        try:
            wifi = subprocess.Popen(['iwgetid','--raw'], stdout=subprocess.PIPE).communicate()[0].strip()
        except OSError:
            wifi = None
        return wifi

    def atwork(self):
        return self.wifi() in ContextHandler.work_wifi

    def athome(self):
        return self.wifi() in ContextHandler.home_wifi

    def weekday(self):
        return not (self.dow() ==6 or self.dow() == 7)

    def dow(self):
        return datetime.date.today().isoweekday()

    def hour(self):
        return datetime.datetime.now().hour

    def __init__(self, tags):
        self.tags = tags

    def refresh(self):
        """ Remove stale tags, add more current ones """
        new_tags = []
        for t in self.tags: # strip out auto_tags
            if t not in ContextHandler.auto_tags:
                new_tags += [t]
        for t in ContextHandler.auto_tags:
            if ContextHandler.auto_tags[t](self):
                new_tags += [t]
        self.tags = new_tags

    def get_tags(self):
        return self.tags

def indent_count(s):
    r""" return number of tabs at start of line
    >>> indent_count('\t\t\tHello')
    3
    >>> indent_count('\tGoodbye')
    1
    >>> indent_count('Nothing')
    0
    """
    return len(s) - len(s.lstrip('\t'))

class TodoError(Exception):
    pass

class Todo:
    r""" Get string from ordered outline list, go up and find parents save parents in self.above.
    >>> l = ['no0', '\tno1', 'yes0', '\tno1', '\t\tno2', '\tyes1', '\t\tyes2', '\t\tno2', '\tno1', 'no0' ]
    >>> i = Todo(l, 6)
    >>> print i.above
    ['yes0', '\tyes1', '\t\tyes2']
    >>> print repr(str(i))
    '\t\tyes2'
    >>> print Todo(['#PYTHON','\ttest @FRED'], 1).above
    ['#PYTHON', '\ttest @FRED']
    """
    def __init__(self, l , num):
        d = l[num]
        above = [d]
        indent_above = indent_count(d) - 1
        for n in range(num-1, -1, -1):
            if indent_above < 0:
                break
            if indent_count(l[n]) == indent_above:
                above.append(l[n])
                indent_above -= 1
        above.reverse()
        self.above = above
        self.linenum = num

    def get_todo_line(self):
        r""" Return main todo line 
        >>> Todo(['#PYTHON','\ttest @FRED'], 1).get_todo_line()
        '\ttest @FRED'
        """
        return self.above[-1]

    def set_todo_line(self, s):
        r""" Return main todo line 
        >>> i = Todo(['#PYTHON','\ttest @FRED'], 1)
        >>> i.set_todo_line('\tbah')
        >>> print i.above
        ['#PYTHON', '\tbah']
        """
        self.above[-1] = s

    def __str__(self):
        r"""
        >>> i = Todo(['daddy', '\tsister', '\tme', '\t\tinside' ], 3)
        >>> print len(str(i))
        8
        >>> print str(i).lstrip()
        inside
        """
        return self.get_todo_line()

    def __repr__(self):
        return repr(self.get_todo_line())

    def tags(self):
        r""" 
        >>> i = Todo(['Get my ass to mars @NOW #MARS'] , 0 )
        >>> i.tags()
        ['@NOW', '#MARS']
        >>> z = Todo(['#PYTHON', '\ttest @FRED' ], 1)
        >>> print z.above
        ['#PYTHON', '\ttest @FRED']
        >>> z.tags()
        ['#PYTHON', '@FRED']
        """
        tags = []
        for d in self.above:
            tags += Tag.extract_tags(d)
        return tags

    def add_tag(self, t):
        r""" Add a tag 
        >>> i = Todo(['Get my ass to mars @NOW #MARS'] , 0 )
        >>> i.tags()
        ['@NOW', '#MARS']
        >>> i.add_tag(Tag('@HELLO'))
        >>> print i.tags()
        ['@NOW', '#MARS', '@HELLO']
        >>> i.add_tag(Tag('@HELLO'))
        Traceback (most recent call last):
          ...
        TodoError: @HELLO tag already in todo
        """
        m = [ n.name() for n in self.tags() ]
        if t.name() in m:
            raise TodoError('%s tag already in todo' % t)
        self.set_todo_line( self.get_todo_line()  + ' ' + str(t) )

    def remove_tag(self, t):
        r""" Remove a tag (if possible)
        Tags that are inherited from outlines cannot be removed.
        >>> z = Todo(['#PYTHON', '\ttest @FRED' ], 1)
        >>> z.remove_tag(Tag('@FRED'))
        >>> print z.tags()
        ['#PYTHON']
        >>> z.remove_tag(Tag('#PYTHON'))
        Traceback (most recent call last):
          ...
        TodoError: Can't remove tag #PYTHON
        >>> # Prevent partial name of tag bug
        >>> z = Todo(['#PYTHON', '\ttest @FRED @FRE @FREE' ], 1)
        >>> z.remove_tag(Tag('@FRE'))
        >>> print z.tags()
        ['#PYTHON', '@FRED', '@FREE']
        >>> # Remove tags with arguments
        >>> z = Todo(['#PYTHON', '\ttest @FRED(Monster)' ], 1)
        >>> z.remove_tag(Tag('@FRED'))
        >>> print z.tags()
        ['#PYTHON']
        """
        if t.name() not in self.above[-1]:
            raise TodoError("Can't remove tag %s" % t)
        if t.name() not in [i.name() for i in self.tags()]:
            raise TodoError('Tried to remove nonexistent tag')
        (start, end) = t.find_in(self.above[-1])
        todoline = self.get_todo_line()
        self.set_todo_line( todoline[:start] + todoline[end:] )

    def unset_current(self):
        try:
            self.remove_tag(Tag.current_tag())
        except TodoError:
            print "Could not remove current tag"
        return

    def remove_tags_if(self, l):
        r""" remove tags if lambda(tag) is true 
        >>> z = Todo(['#PYTHON', '\ttest @FRED @FREDY @FREE' ], 1)
        >>> print z.tags()
        ['#PYTHON', '@FRED', '@FREDY', '@FREE']
        >>> z.remove_tags_if(lambda t: t.name().startswith('@FRED'))
        >>> print z.tags()
        ['#PYTHON', '@FREE']
        """
        tags_to_go = [ t for t in self.tags() if l(t) ]
        for i in tags_to_go:
            self.remove_tag(i)
        return 

    def ignore_until(self):
        r"""
        >>> i = Todo(['#PYTHON','\ttest @FRED @IGNOREUNTIL(2005-05-05T12:10)'], 1)
        >>> z = i.ignore_until()
        >>> print z.year
        2005
        """
        m = [i for i in self.tags() if i.is_ignore()]
        if not m:
            return datetime.datetime(datetime.MINYEAR, 1, 1)
        if len(m) != 1:
            raise TodoError("Too many ignore tags")
        t = m[0]
        return datetime.datetime.strptime(t.argument()[0], '%Y-%m-%dT%H:%M') # Move to subclass of Tag?

    def score(self, target_tags):
       return len(set(self.tags()).intersection(target_tags))

class TodoList:
    def __init__(self, l = None):
        if not l or not isinstance(l, list):
            raise Exception, "TodoList needs a list"
        self.contents = l

    def parse_todos(self):
        r""" Find all todos in the todolist
        >>> i = TodoList([',INBOX','\tmust do X','\tmust do Y', ',CONTEXTS', '\t#FRED', '\t\tdo another thing @FOO'])
        >>> i.parse_todos()
        >>> print i.todos
        ['\tmust do X', '\tmust do Y', '\t\tdo another thing @FOO']
        >>> print i.todos[-1].tags()
        ['#FRED', '@FOO']
        """
        todos = []
        tags = {}
        state = 'TOP_LEVEL'
        contents_copy = self.contents[:len(self.contents)]
        for i in range(0, len(contents_copy)):
            l = contents_copy[i]
            ind = indent_count(l)
            if ind == 0:
                state = 'TOP_LEVEL'
                todo_level = -1
            if l == ',INBOX':
                state = 'TODO'
                todo_level = 1
                continue
            if l == ',PROJECTS':
                state = 'TODO'
                todo_level = 2
                continue
            if l == ',CONTEXTS':
                state = 'TODO'
                todo_level = 2
                continue
            if state == 'TODO' and ind == todo_level:
                todo = Todo(contents_copy, i)
                todos += [todo]
                for i in todo.tags():
                    tags.setdefault(i, [])
                    tags[i] += [todo]
        self.tags = tags
        self.todos = todos

    def top_todo(self, contexts= []):
        self.parse_todos()
        ct = self.current_todo()
        time_now = datetime.datetime.now()
        if ct:
            return ct
        context_score = 0
        best_bet = None
        tag_set = set(contexts)
        randomizing_count = 1
        for i in contexts:
            todos_in_context = self.tags.setdefault(i, [])
            for j in todos_in_context:
                if j.ignore_until() > time_now:
                    continue
                this_score = j.score(tag_set)
                if this_score >= context_score:
                    randomizing_count += 1
                    if this_score > context_score:
                        randomizing_count  = 1
                    if random.random() > (1.0/randomizing_count):
                        continue
                    context_score = this_score
                    best_bet = j
        if not best_bet:
            best_bet = random.choice(self.todos)
        self.contents[best_bet.linenum] += ' ' + Tag.current_tag()
        self.sync()
        return best_bet

    def split_todo(self, original, addition):
        r"""
        >>> i = TodoList([',INBOX','\tmust do X','\tmust do Y @CURRENT', ',CONTEXTS', '\t#FRED', '\t\tdo another thing @FOO'])
        >>> i.split_todo(i.current_todo(), '\tthen do Z')
        >>> j = i.contents
        >>> j[1]
        '\tmust do X'
        >>> j[2]
        '\tmust do Y @CURRENT'
        >>> j[3]
        '\tthen do Z'
        >>> j[4]
        ',CONTEXTS'
        """
        """ Given an original todo, insert a new one underneath it """
        self.contents[original.linenum:original.linenum+1] = [str(original), str(addition)]
        self.sync()

    def add_new_todo(self, newtodo):
        r"""
        >>> i = TodoList([',INBOX','\tmust do X','\tmust do Y @CURRENT', ',CONTEXTS', '\t#FRED', '\t\tdo another thing @FOO'])
        >>> i.add_new_todo("Hello")
        True
        >>> j = i.contents
        >>> j[0]
        ',INBOX'
        >>> j[1]
        '\tHello'
        >>> j[2]
        '\tmust do X'
        """
        for l in range(0, len(self.contents)):
            if self.contents[l].strip() == ',INBOX':
                num_tabs = indent_count(self.contents[l]) + 1
                indented_todo = '\t' * num_tabs + newtodo
                self.contents[l:l + 1] = [',INBOX', indented_todo]
                self.sync()
                return True
        return False

    def current_todo(self):
        r"""
        >>> i = TodoList([',INBOX','\tmust do X @CURRENT','\tmust do Y', ',CONTEXTS', '\t#FRED', '\t\tdo another thing @FOO'])
        >>> 'must do X' in str(i.current_todo())
        True
        """
        self.parse_todos()
        ct = self.tags.setdefault(Tag.current_tag(), [])
        if not ct:
            return None
        if len(ct) > 1:
            raise TodoError, "More than one current todos! Ulp!"
        return ct[0]

    def timestamped_append_to_bottom(self, l):
        l2 = '\t'+timestamp()+" " + l.lstrip()
        self.contents[-1:] = [self.contents[-1], l2 ]
        self.sync()

    def mark_current_done(self):
        r"""
        >>> i = TodoList([',INBOX','\tmust do X @CURRENT','\tmust do Y', ',CONTEXTS', '\t#FRED', '\t\tdo another thing @FOO'])
        >>> i.mark_current_done()
        >>> i.contents[0:3] 
        [',INBOX', '\tmust do Y', ',CONTEXTS']
        >>> 'must do X' in i.contents[-1]
        True
        >>> '@CURRENT' not in i.contents[-1]
        False
        """
        current_todo = self.current_todo()
        l = current_todo.linenum
        current_todo.unset_current() # remove current tag
        current_todo.remove_tags_if(lambda x: x.same_name_as(Tag.ignore_tag())) # remove ignore tags
        repeat_tag = [ t for t in current_todo.tags() if t.is_repeat() ] 
        done = self.contents[l]
        if repeat_tag:
            # create ignoreuntil from this point
            ignore_tag = repeat_tag[0].ignore_from_repeat(datetime.datetime.now())
            current_todo.add_tag(ignore_tag)
            self.contents[current_todo.linenum] = str(current_todo)
            self.sync()
        else:
            # remove entry from current position
            # FIXME deal with multi-line todos
            self.contents[l:l+2] = [self.contents[l+1]]
            # put timestamped copy at end of file
            self.timestamped_append_to_bottom(done)

    def get_all_tags(self):
        self.parse_todos()
        return self.tags.keys()

    def get_all_todos(self):
        self.parse_todos()
        return self.todos

    def sync(self):
        pass

class TodoListVim(TodoList):
    def __init__(self, l=None):
        if l == None:
            vb = vimhelper.VimBuffer('TODO', 'todo.txt')
        else:
            raise Exception, "Don't know how to open specific Vim instances yet"
        self.contents = vb

class TodoListFile(TodoList):
    def __init__(self, l="~/todo.txt"):
        self.filename = os.path.expanduser(l)
        f=file(self.filename,'r')
        self.contents = [i.rstrip() for i in f.readlines()]

    def sync(self):
        print("Syncing " + self.filename)
        filename = self.filename
        if os.path.islink(filename):
            linkname = os.readlink(filename)
            filename = os.path.join(os.path.dirname(self.filename),linkname)
        filename_tmp = filename+"~"
        # when this screws up, you should probably add some file locking
        f=open(filename_tmp, 'w')
        f.writelines([i+'\n' for i in self.contents])
        f.close()
        os.rename(filename_tmp, filename)

def DefaultTodoList():
    try:
        return TodoListVim()
    except vimhelper.VimBufferNotFound:
        return TodoListFile()
 
def main(args):
    """ Put your main command line runner here """
    pass

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
