:function! GetTopTodo()
call search("^,INBOX")
normal j0
return getline(".")
:endfunction

:function! AppendTodos()
python <<EOF
from vim import *
for i in buffers:
    if ('todo.txt' in str(i.name)):
        todo = i
urgent = []
for i in todo:
    if ('\t*' in str(i)):
        urgent.append(i)
#urgent has a list of urgent todos
current.buffer.append(urgent)
EOF
:endfunction

:function! AppendDone()
python <<EOF
from vim import *
for i in buffers:
    if ('todo.txt' in str(i.name)):
        todo = i
done = []
for i in todo:
    if ('\tx ' in str(i)):
        done.append(i)
#urgent has a list of urgent todos
current.buffer.append(done)
EOF
:endfunction

:function! ShelveTodo()
:if match(getline("."),"\t=") != -1
    :normal "xyy
    :else
    :normal "xddk
:endif
:normal mt
:normal /^,DONE/
:normal /^,/
:normal k"xp0l,d 
:normal g'tj
:endfunction

:function! FileTodo()
:normal "uyiW
:if foldlevel(line(".")) > 1
:normal zvzc
:endif
:normal "edd
:let tag=@u
:let todo=@e
:if strpart(tag, 0, 1) != "#" && strpart(tag, 0, 1) != "@"
:   let tag=matchstr(todo, '#\w\+')
:   let @u=tag
:endif
:normal mt
:if strpart(tag, 0, 1) == "#"
:/^,PROJECTS
:elseif strpart(tag, 0, 1) == "@"
:/^,CONTEXT
:else
:   throw "Could not find tag"
:endif
:normal mm    
:normal /^,me 
:normal g'm
:let tagpos=search('^\t'.tag, 'We', line("'e"))
:if tagpos == 0
    :normal o	"up
:endif
:let @f=substitute(@e,"\n\t","\n\t\t","g")
:let @f=substitute(@f,"^\t","\t\t","g")
:normal "fp
:normal g'tj
:endfunction

:function! CopyTodo()
:normal "xyy/^,DONE/
:normal /^,/
:normal k"xp0l,d 
:endfunction

:function! GrowlLine()
python << EOF
import vim
import os
import datetime
l = vim.current.line
os.system("/usr/bin/notify-send '%s' -h int:x:0 -h int:y:20" % l.lstrip())
EOF
:endfunction


:map ,,p :call FileTodo()
:map ,,P :call FileTodo()
:map ,,F :call FileTodo()
:map ,,f :call FileTodo()
:map ,,X :call ShelveTodo()
:map ,,x :call ShelveTodo()
:map ,,c :call CopyTodo()
:map ,,g :call GrowlLine()

:set foldcolumn=0
