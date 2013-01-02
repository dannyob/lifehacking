#!/usr/bin/env python
##
# pavement.py
###
"""pavement.py

"""

__version__ = "0.1"
__author__ = "Danny O'Brien <http://www.spesh.com/danny/>"
__copyright__ = "Copyright Danny O'Brien"
__contributors__ = None
__url__ = "http://www.oblomovka.com/public/lifehacking/pavement.py"
__license__ = "GPL"

import os.path

import todo
import datetime
import subprocess
from paver.easy import *

MINIMUM_PRIORITY = 0
DEFAULT_PRIORITY = 50 # out of 100
MEDIUM_PRIORITY = 75
TOP_PRIORITY = 100
TWEAK_PRIORITY = 10 # tweaking up or down

private_store = os.path.expanduser('~/Private/lifehacking/')
if not os.path.exists(private_store):
    os.makedirs(private_store)

def store_setting(key, value):
    f = file(os.path.expanduser('~/Private/lifehacking/'+key),'w')
    print >>f, value
    f.close()

def get_setting(key):
    """
    >>> store_setting('test', 'result')
    >>> print get_setting('test')
    result
    >>> print get_setting('nonexistent')
    None
    """
    try:
        f = file(os.path.expanduser('~/Private/lifehacking/'+key),'r')
        i = f.read().rstrip()
        f.close()
        return i
    except IOError:
        return None


class Order():
    def __init__(self, description="No orders", command='', alt_command='', priority=DEFAULT_PRIORITY):
        self.description = str(description)
        self.command = command
        self.alt_command = alt_command
        self.priority = priority

    def set_priority(self, value):
        self.priority = value

    def __str__(self):
        return self.description
    
options(
        human=Bunch(
            order = Order(description="Nothing to do",priority=MINIMUM_PRIORITY),
            )
        )

last_order = get_setting('last_order')

def set_order(o):
    if str(o) == last_order: # this is what we had last time! keep it!
        options.human.order = o
    if o.priority > options.human.order.priority:
        options.human.order = o


@task
@needs('bedtime')
@needs('testtask')
@needs('todolist')
@needs('unreadmail')
@needs('autocontext')
def now():
    """ Tell Danny what to do """
    announce= todo.timestamp() + " " + str(options.human.order).lstrip()
    print(announce)
    store_setting('last_order', str(options.human.order))

@task
@needs('now')
def osd():
    """ Show last order on screen """
    this_order = get_setting('last_order')
    subprocess.call(["gtodo", this_order])   

@task
def testtask():
    set_order( Order('Test task',priority= MINIMUM_PRIORITY))

@task
def todolist():
    """ Scan todo.txt """
    pr = DEFAULT_PRIORITY
    tags = get_tags()
    t = todo.DefaultTodoList().top_todo(tags)
    if t == None:
       return
    if '@URGENT' in str(t):
        pr = TOP_PRIORITY
    set_order(Order(t,'','todo_top_split', priority=pr))

import re
inbox = os.environ['MAILDIR']
if not os.path.exists(inbox):
    inbox = None

@task
def bedtime():
    """ Stop myself working all night """
    n = datetime.datetime.now()

    if n.hour > 22 or n.hour < 8:
        set_order(Order('Sleeeeeeeeeeeep is gooooooooooood', priority=TOP_PRIORITY))

@task
def unreadmail():
    """ Pluck out unread mail """
    global inbox
    if not inbox:
        return
    inbox="notmuch"
    inbox_zero_plus = 70
    inbox_zero_toomuch = 100
    inbox_chance = 0.2 # 1 in 5 tasks should be answering email
    import mailbox
    if inbox=="notmuch":
        os.system('notmuch-mutt search "tag:flagged OR (tag:inbox AND tag:recently AND NOT tag:archive AND NOT tag:lists)" > /dev/null 2>&1')
        inbox=os.path.expanduser("~/.cache/notmuch/mutt/results")
    m = mailbox.Maildir(inbox)
    if len(m) == 0:
        return
    if len(m) > inbox_zero_toomuch:
        pr = TOP_PRIORITY
        inbox_chance = 0.5 # bring up the chances until we've dealt with backlog
    elif len(m) > inbox_zero_plus:
        pr = MEDIUM_PRIORITY
    else:
        pr = DEFAULT_PRIORITY
    if (random.random() > inbox_chance):
        return
    mail_key = m.keys()[0]
    mail = m[mail_key]
    topmail=file(os.path.expanduser('~/.topmail'),'w')
    message_id = mail['message-id']
    message_id = re.sub(r'[<>]','', message_id)
    message_id = re.sub(r'\]|\[|\*|\.|\+|\$','.', message_id)
    print >>topmail, message_id
    set_order( Order('Deal with mail from %s about %s' % (mail['From'], mail['Subject']), 'tm', priority=pr) )

def get_tags():
    tags = get_setting('current_context')
    if tags: 
        return tags.split(',')
    else:
        return []

def set_tags(newtags):
    tags = ','.join(newtags)
    tags= tags.upper()
    store_setting('current_context', tags )

@task
@consume_args
def context():
    """ Change the stored context(s) right now """ 
    tags = options.args
    print "Changing contexts to: ", tags
    set_tags( tags )

@task
@consume_args
def split():
    """ Splits the current task into two """
    subtask = " ".join(options.args)
    tags = get_tags()
    t =  todo.DefaultTodoList()
    toptodo = t.top_todo(tags)
    if not toptodo:
        print "Don't know current task!"
    print "Splitting ",toptodo
    todo_tags = todo.Tag.extract_tags(str(toptodo)) 
    if todo.Tag.current_tag() not in todo_tags: 
        raise Exception, "Where is current tag?"
        todo_tags += [todo.Tag.current_tag()]
    subtask += ' ' + ' '.join(todo_tags)
    subtask = '\t' * todo.indent_count(str(toptodo)) + subtask
    toptodo.unset_current()
    if todo.Tag.urgent_tag() in todo_tags:
        visit_next = datetime.datetime.now() + datetime.timedelta(hours=2)
    else:
        visit_next = datetime.datetime.now() + datetime.timedelta(days=2)
    try:
        toptodo.add_tag(todo.Tag.ignore_tag(visit_next))
    except todo.TodoError: # assume we can't add because there's already a ignore tag
        toptodo.remove_tag(todo.Tag.ignore_tag(visit_next))
        toptodo.add_tag(todo.Tag.ignore_tag(visit_next))
    t.split_todo(toptodo, subtask)

@task
def done():
    """ Marks current task as done """
    t = todo.DefaultTodoList()
    t.mark_current_done()

@task
def autocontext():
    """ Automatically refresh tags """
    tags = get_tags()
    ch = todo.ContextHandler(tags)
    ch.refresh()
    new_tags = ch.get_tags()
    print "Changing tags from ", tags, " to ", new_tags
    set_tags(new_tags)
    

def filter_tags(f, tags):
    """ Filter tags leaving only project or context tags,
    also room for other starter characters.
    """
    if f == 'PROJECT':
        f = '#'
    if f == 'CONTEXT':
        f = '@'
    c = [i for i in tags if i[0] == f ]
    return c

@task
def listcontexts():
    """ List all contexts in todo list """
    print '\n'.join(filter_tags('CONTEXT', todo.DefaultTodoList().get_all_tags() ))
 
@task
def listprojects():
    """ List all projects in todo list """
    print '\n'.join(filter_tags('PROJECT', todo.DefaultTodoList().get_all_tags() ))

@task
def listtodos():
    z= todo.DefaultTodoList().get_all_todos()
    for i in z:
        print i, i.score(get_tags())
    print
    print "Todos Total: ", len(z)

import random
@task
def randomproject():
    """ Settle on a random project """
    random.seed()
    tags = filter_tags('CONTEXT', get_tags()) # filter out projects
    project_tag = random.choice(filter_tags('PROJECT', todo.DefaultTodoList().get_all_tags() )) # random pick from all projects
    tags = tags + [ project_tag ]
    print "Tags changed from ", get_tags(), " to ", tags
    set_tags(tags)
