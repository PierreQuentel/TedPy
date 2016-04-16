# -*- coding: utf-8 -*-

import sys
import os
import threading
import re
import string
import time
import keyword
import configparser

from tkinter import *
from tkinter.filedialog import *
import tkinter.messagebox
import tkinter.simpledialog
from tkinter.font import Font
from tkinter.scrolledtext import ScrolledText

version = "1.0"

import translation
translation.language = 'fr'
_ = translation.translate

python_versions = [ ('Python %s.%s' %sys.version_info[:2],sys.executable)]
encodings = ['ascii','iso-8859-1','latin-1','utf-8','cp850']

# config
ini = configparser.ConfigParser(allow_no_value=True)
ini.read(['config.ini'],encoding='utf-8')
if ini.has_section('versions'): # Python versions
    for vnum in ini.options('versions'):
        python_versions.append((vnum.capitalize(),ini.get('versions',vnum)))
if ini.has_section('encodings'):
    for encoding in ini.options('encodings'):
        if not encoding in encodings:
            encodings.append(encoding)

# parameters
history_size = 8 # number of files in history
wheel_coeff = 2 # increase wheel scrolling
spaces_per_tab = 4

root = Tk() # needed here for font definitions
root.title("TedPy")

# global variables
current_doc = None
wheel_delta = None
docs = []

# syntax highlighting parameters
square_brackets = r'[\[\]]'
curly_braces = r'[\{\}]'
parenthesis = r'[\(\)]'
patterns = {'.html':[],
    '.js':[]} # for Python, set by make_patterns()
for lang in patterns:
    patterns[lang]+=[(square_brackets,'square_bracket'),
        (parenthesis,'parenthesis'),(curly_braces,'curly_brace')]
from js_keywords import js_keywords
js_keywords = [ (r'\b'+kw+r'\b') for kw in js_keywords ]
patterns['.js'].append(('|'.join(js_keywords),'keyword'))
zones = {'.py':[ ('"""','"""','string'),('"','"','string'),("'","'",'string'),
        ('#','\n','comment')],
    '.js':[('"','"','string'),("'","'",'string'),('//','\n','comment'),
        ('/*','*/','comment')],
    '.html':[]
    }

class EncodingError(Exception):
    pass

class Document:

    num = 1

    def __init__(self,file_name,ext=None,text=""):
        self.has_name = file_name is not None
        self.file_name = file_name
        if file_name is None:
            self.file_name = os.path.normpath(os.path.join(default_dir(),
                    "module%s.%s" %(Document.num,ext)))
            Document.num += 1
        self.text = text

class EncodingChooser(tkinter.simpledialog._QueryDialog):

    def body(self,master):
        w = Label(master, text=self.prompt, justify=LEFT)
        w.grid(row=0, padx=5, sticky=W)
        for i,enc in enumerate(enc for enc in encodings if enc != self.initialvalue.get()):
            Radiobutton(master,text=enc,variable=self.initialvalue,
                value=enc,padx=15).grid(row=1+i,sticky=W)

    def getresult(self):
        return self.initialvalue.get()
    
class Editor(Frame):

    def __init__(self):
        frame = Frame(panel,relief=GROOVE,borderwidth=4)
        
        bar_bg = '#666'

        shortcuts = Frame(frame, bg=bar_bg)
        for (src,callback) in [('⤶',self.undo),('⤷',self.redo),
            ('≡',self.change_wrap)]:
            widget = Label(shortcuts,text=src,relief=RIDGE,bg="#FFF",
                foreground="#000",font=sh_font)
            widget.bind('<Button-1>',callback)
            widget.pack(side=LEFT,anchor=W)
        
        widget = Button(shortcuts,text='X',font=sh_font,relief=RIDGE)
        widget.bind('<Button-1>',_close)
        widget.pack(side=RIGHT,anchor=E)
        Label(shortcuts,text='    ',bg=bar_bg).pack(side=RIGHT)
        self.label_line = Label(shortcuts,text='1', font=font, fg='#fff', bg=bar_bg)
        self.label_column = Label(shortcuts,text='1', font=font, fg='#fff', bg=bar_bg)
        self.label_column.pack(side=RIGHT)
        Label(shortcuts,text=' | ',bg=bar_bg, fg='#fff').pack(side=RIGHT)
        self.label_line.pack(side=RIGHT)
        self.encoding = StringVar()
        enc_label = Label(shortcuts,textvariable=self.encoding,relief=RAISED,font=font)
        enc_label.bind('<Button-1>',self.set_encoding)
        enc_label.pack(side=RIGHT)
        shortcuts.pack(fill=BOTH)
        bg = '#222222' # background colour
        
        zone = ScrolledText(frame,width=text_width-3,
            font=default_font,wrap=NONE,relief=FLAT,undo=True,
            autoseparators=True,bg=bg,foreground='white',
            insertbackground="white", selectbackground='#630')
        zone.vbar.config(command=self.slide)
        line_height = zone.dlineinfo(1.0)[-1] # in pixels
        text_height = int(root_h/line_height)
        zone['height'] = text_height
        
        hbar = Scrollbar(frame, name='hbar',orient=HORIZONTAL,bg="red")
        hbar.pack(side=BOTTOM, fill=BOTH, expand=YES)
        hbar['command'] = zone.xview
        zone['xscrollcommand'] = hbar.set
        
        line_nums=Text(frame,width=3,background=bg,
            selectbackground="#FFFFFF",foreground="#808080",
            relief=FLAT,state=DISABLED)
        line_nums.pack(side=LEFT,fill=BOTH)
        line_nums.bind('<Button-1>',self.click_line_nums)

        zone.bind('<Key>',self.key_pressed)
        zone.bind('<KeyRelease>',self.update)
        zone.bind('<MouseWheel>',self.wheel)
        zone.bind('<Tab>',self.insert_tab)
        zone.bind('<Shift-Tab>',self.remove_tab)
        zone.bind('<Return>',self.insert_cr)
        zone.bind('<Button-1>',self.click)
        zone.bind('<Leave>',self.leave)
        zone.bind('<Enter>',self.enter)
        zone.bind('<ButtonRelease-1>',self.button_release)
        zone.bind('<Button-3>',self.right_click)
        zone.bind('<Control-KeyRelease-v>',self.paste)
        zone.bind('<Control-Key>',self.set_control)
        zone.bind('<Configure>',self.print_line_nums)
        zone.bind('<Home>',self.home)

        zone.tag_config('comment',foreground="#00A000")
        zone.tag_config('string',foreground="#60A0A0")
        zone.tag_config('keyword',foreground="#9999FF")
        zone.tag_config('builtin',foreground="#00FF00")
        zone.tag_config('balise',foreground="#F00080")
        zone.tag_config('parenthesis',foreground="#FF00FF")
        zone.tag_config('curly_brace',foreground="#FF0000",font=curly_font)
        zone.tag_config('square_bracket',foreground="#338800")
                
        zone.tag_config('found',foreground=bg,background="white")
        zone.tag_config('selection',background=zone['selectbackground'])
        zone.tag_bind(SEL,'<Enter>',self.enter_sel)
        
        zone.pack(expand=YES,fill=BOTH)

        self.zone = zone
        self.frame = frame
        self.line_nums = line_nums
        self.shift = False
        self.control = False
        self.click_on_sel = False
        self.last_update = None

    def set_encoding(self,event):
        self.prev_enc = self.encoding.get()
        menu = Menu(self.zone,tearoff=False)
        for encoding in encodings:
            menu.add_radiobutton(label=encoding,variable=self.encoding,
                command=self.change_encoding)
        menu.post(event.x_root,event.y_root)

    def change_encoding(self):
        new_enc = self.encoding.get()
        # Check that the document can be encoded in the new encoding
        src = self.zone.get(1.0,END)
        try:
            src.encode(new_enc)
        except:
            tkinter.messagebox.showinfo(title=_('Encoding error'),
                message=_('not encoding') %self.prev_enc)
        
    def click_line_nums(self,event):
        line = self.line_nums.index(CURRENT).split('.')[0]
        self.zone.mark_set(INSERT,'%s.0' %line)
        self.zone.focus()
        return 'break'

    def print_line_nums(self,*args):
        w_height = int(self.zone.winfo_geometry().split('+')[0].split('x')[0])
        nb_lignes = int(self.zone.index('%s-1c' %END).split('.')[0])
        _format = '{:%sd}' %len(str(nb_lignes+1))
        # find visible lines
        lines = []
        for x in range(1,nb_lignes+1):
            bbox = self.zone.dlineinfo(self.zone.index('%s.0' %x))
            if bbox: # line is visible
                lines.append((x,bbox))
            elif lines:
                break
        self.first_visible,self.last_visible = lines[0][0],lines[-1][0]
        self.line_nums.config(state=NORMAL)
        self.line_nums.delete(1.0,END)
        self.line_nums['width'] = 1+len(str(nb_lignes+1))
        self.zone['width'] = text_width-self.line_nums['width']
        first_offset = offset = lines[0][1][1]
        char_height = self.line_nums.bbox('1.0')[3] # line height in pixels
        for line_num,bbox in lines:
            nb = (bbox[1]-offset)/char_height
            self.line_nums.insert(END,'\n'*int(nb-1)) # empty lines
            self.line_nums.insert(END,(_format.format(line_num))+'\n')
            offset = bbox[1]
        last_line_height = (w_height-lines[-1][1][1])/char_height
        self.line_nums.insert(END,'\n'*int(last_line_height-1))
        self.line_nums.insert(END,'\n'*10) # to be able to move vertically
        # compute line nums offset to be aligned with text
        nb_line_nums = int(self.line_nums.index(END).split('.')[0])
        line_nums_height = char_height*nb_line_nums
        first_line_num_offset = self.line_nums.bbox('1.0')[1]
        move = (first_line_num_offset-first_offset)/line_nums_height
        self.line_nums.yview(MOVETO,move)
        self.line_nums.config(state=DISABLED)

    def delayed_sh(self):
        # delayed syntax highlighting, launched by a timer
        if docs and self.do_delayed:
            self.syntax_highlight(True)

    def syntax_highlight(self,delayed=False):
        file_browser.mark_if_changed()
        self.highlight = syntax_highlight.get()
        if not syntax_highlight.get():
            # remove existing tags
            for tag in self.zone.tag_names():
                self.zone.tag_remove(tag,1.0,END)
            return
        # check encoding
        try:
            self.zone.get(1.0,END).encode(self.encoding.get())
        except UnicodeError:
            tkinter.messagebox.showerror(title=_("unicode error"),
                    message=_("can't encode with %s") %self.encoding.get())
            self.zone.delete(self.zone.index("%s-1c" %INSERT))

        file_name = docs[current_doc].file_name
        ext = os.path.splitext(file_name)[1]
        self.font = font.get(ext,default_font)
        self.zone.config(font=self.font)
        self.line_nums.config(font=self.font)
        if not ext in patterns:
            return
        # don't do highlighting too often
        if self.last_update and time.time()-self.last_update < 0.2:
            self.do_delayed = True
            # set a timer that will do a syntax highlight in 500 ms
            # if nothing was entered in the meantime
            self.zone.after(500,self.delayed_sh)
            return
        self.do_delayed = False
        txt = self.zone.get(1.0,END).rstrip()+'\n'
        ltxt = list(txt)
        # mapping between position and line,column
        lc = []
        line,col = 1,0
        for car in txt:
            lc.append((line,col))
            col += 1
            if car == '\n':
                line += 1
                col = 0
        # remove existing tags
        for tag in self.zone.tag_names():
            self.zone.tag_remove(tag,1.0,END)
        # parse text to find strings, comments, keywords
        pos = 0
        while pos < len(txt):
            flag = False
            for start,stop,ztype in zones[ext]:
                if txt[pos:pos+len(start)] == start:
                    spos = pos+len(start)
                    while True:
                        end = txt.find(stop,spos)
                        if end != -1 and txt[end-1]=='\\' and txt[end-2]!='\\':
                            spos = end+1
                        else:
                            break
                    if end>-1:
                        # set zone to whitespace for next markup
                        for i in range(pos,end+len(stop)):
                            ltxt[i]=" "
                        # highlight zone with matching tag
                        ix1 = '%s.%s' %lc[pos]
                        ix2 = '%s.%s' %lc[min(end+len(stop),len(txt)-1)]
                        self.zone.tag_add(ztype,ix1,ix2)
                        pos = end+len(stop)
                        flag = True
                    break # if """ matched, don't try a single "
            if not flag:
                pos += 1
        raw = ''.join(ltxt) # original text with empty strings and comments
        for (pattern,tag) in patterns[ext]:
            for mo in re.finditer(pattern,raw,re.S):
                k1,k2 = mo.start(),mo.end()
                self.zone.tag_add(tag,'%s.%s' %lc[k1],'%s.%s' %lc[k2])
        self.last_update = time.time()
        
    def click(self,event):
        self.zone.tag_remove('selection',1.0,END)
        self.zone.tag_remove('found',1.0,END)
        # if click on a selected zone, mark possible drag and drop start
        if SEL in self.zone.tag_names(CURRENT):
            start,end = self.zone.tag_ranges(SEL)
            if self.zone.index(end)==self.zone.index(END) \
                and self.zone.index(start)=='1.0':
                    return
            self.click_on_sel = True
            self.zone['cursor'] = "arrow"
            self.selected_text = self.zone.get(*self.zone.tag_ranges(SEL))
            return 'break'
            
    def enter_sel(self,*args):
        self.zone['cursor']='arrow'

    def leave(self,event):
        if self.click_on_sel:
            return 'break'

    def enter(self,event):
        if self.click_on_sel:
            return 'break'

    def button_release(self,event):
        if self.click_on_sel:
            if not SEL in self.zone.tag_names(CURRENT):
                self.zone.insert(CURRENT,self.selected_text)
                self.zone.delete(*self.zone.tag_ranges(SEL))
            self.zone.tag_remove(SEL,1.0,END)
        self.click_on_sel = False
        self.zone['cursor'] = 'xterm'
        self.update_line_col()
                        
    def update_line_col(self,*args):
        self.current_line,column = map(int,self.zone.index(INSERT).split('.'))
        self.label_line['text'] = str(self.current_line)
        self.label_column['text'] = str(column+1)

    def key_pressed(self,event):
        if event.keysym in ['Shift_R','Shift_L']:
            self.shift = True
        elif event.keysym in ['Control_L','Control_R']:
            self.control = True

    def update(self,event):
        if event.keysym == 'Tab':
            return 'break'
        if self.control:
            if event.keysym.lower()== "a":
                self.zone.tag_add(SEL,1.0,END)
            elif not event.keysym.lower()=="c":
                self.zone.tag_remove(SEL,1.0,END)
            self.control = False
            return 'break'
        self.update_line_col()
        self.zone.see(INSERT)
        if self.shift:
            if event.keysym in ['Shift_R','Shift_L']:
                self.shift = False
            return
        if not event.keysym in ['Up','Down','Left','Right','Next','Prior',
            'Home','End','Control_L','Control_R']:
            self.syntax_highlight()
        if not event.char:
            if event.keysym in ['Next','Prior','BackSpace','Delete'] \
                or self.current_line < self.first_visible \
                or self.current_line > self.last_visible:
                self.print_line_nums()

    def wheel(self,event):
        global wheel_delta
        if event.delta != 0:
            if wheel_delta is None or abs(event.delta)<wheel_delta:
                wheel_delta = abs(event.delta)/ wheel_coeff
            delta = -event.delta / wheel_delta
            self.slide('scroll',int(delta),'units')
        return "break" # don't propagate

    def slide(self,*args):
        self.zone.yview(*args)
        self.print_line_nums()

    def insert_tab(self,event): # replace tabs by 4 spaces
        sel = self.zone.tag_ranges(SEL)
        if not sel:
            self.zone.insert(INSERT,' '*spaces_per_tab)
        else:
            first_line,last_line = [int(self.zone.index(x).split('.')[0]) 
                for x in sel]
            if self.zone.index(sel[1]).endswith('.0'):
                last_line -= 1
            for line in range(first_line,last_line+1):
                self.zone.insert(float(line),' '*spaces_per_tab)
        return 'break'

    def remove_tab(self,event): # shift selected zone to the left by 4 spaces
        sel = self.zone.tag_ranges(SEL)
        if not sel:
            nb = spaces_per_tab
            while nb and self.zone.get(INSERT)==' ':
                self.zone.delete(INSERT)
                nb -=1
        else:
            first_line,last_line = [int(self.zone.index(x).split('.')[0]) 
                for x in sel]
            if self.zone.index(sel[1]).endswith('.0'):
                last_line -= 1
            for line in range(first_line,last_line+1):
                nb = spaces_per_tab
                while nb and self.zone.get(float(line))==' ':
                    self.zone.delete(float(line))
                    nb -=1
        return 'break'

    def insert_cr(self,event): # autoindent
        selected = self.zone.tag_ranges(SEL)
        if selected: # remove selection
            start,end = selected
            self.zone.delete(*selected)
            if self.zone.index(end).endswith('.0'):
                self.zone.delete(start)
        pos = self.zone.index(INSERT)
        start = self.zone.index('%slinestart' %pos)
        txt = self.zone.get(start,pos)
        indent = len(txt)-len(txt.lstrip())
        self.zone.insert(INSERT,'\n'+indent*' ')
        self.print_line_nums()
        return 'break'

    def paste(self,event):
        self.syntax_highlight()
        self.print_line_nums()
        return 'break'

    def set_control(self,event):
        self.control = True

    def home(self,event):
        # go to start of line, after the indentation
        left = self.zone.get('%slinestart' %self.zone.index(INSERT),INSERT)
        if not left.strip(): # only spaces at the left of INSERT
            return
        nbspaces = len(left)-len(left.lstrip())
        self.zone.mark_set(INSERT,'%slinestart+%sc'
             %(self.zone.index(INSERT),nbspaces))
        return 'break'

    def right_click(self,event):
        ext = os.path.splitext(docs[current_doc].file_name)[1]
        if ext == '.py':
            kws = ['def','class']
        elif ext == '.js':
            kws = ['function']
        else:
            return
        current = self.zone.index(CURRENT)
        if current == self.zone.index(current+'lineend'):
            # menu to reach all functions, classes and methods in the script
            browser = Menu(root,tearoff=0,relief=FLAT,background="orange")
            lines = [x.rstrip() for x in self.zone.get(1.0,END).split('\n')]
            for i,line in enumerate(lines):
                for kw in kws:
                    if line.lstrip().startswith(kw+' '):
                        label,num = line[:line.find('(')],i+1
                        browser.add_radiobutton(label=label,variable=target,
                            value=num,command=self.goto)
                        target.set(None) # to deselect the button
            browser.yposition(10)
            browser.post(event.x_root,event.y_root)
        else:
            if not self.zone.get(current+'linestart',current).strip():
                return # click on indentation
            if set(self.zone.tag_names(current)) & \
                set(['string','comment','keyword','def_class']):
                return
            start = self.zone.search(r'[^\w]',CURRENT,backwards=True,
                stopindex=current+'linestart',regexp=True) \
                or current+'linestart'
            if start != current+'linestart':
                start = start+'+1c'
            end = self.zone.search(r'\M',CURRENT,regexp=True,
                stopindex=current+'lineend') or current+'lineend'
            word = self.zone.get(start,end)
            kwp = '|'.join(kws)
            pos = self.zone.search(r'^ *(%s)\s+%s' %(kwp,word),1.0,regexp=True)
            # menu to reach a class, method or function
            if pos:
                label = self.zone.get(pos,pos+'lineend')
                num = int(pos.split('.')[0])
                browser = Menu(root,tearoff=0,relief=FLAT,
                    background="orange")
                browser.add_radiobutton(label=label,variable=target,
                    value=num,command=self.goto)
                browser.post(event.x_root,event.y_root+5)

    def goto(self,*args):
        line_num = target.get()
        self.zone.focus()
        self.zone.mark_set(INSERT,'%s.0' %line_num)
        self.zone.see(INSERT)
        self.print_line_nums()

    def undo(self,*args):
        try:
            self.zone.edit_undo()
            self.syntax_highlight()
        except:
            pass

    def redo(self,*args):
        try:
            self.zone.edit_redo()
            self.syntax_highlight()
        except:
            pass

    def change_wrap(self,*args):
        if self.zone['wrap'] == NONE:
            self.zone.config(wrap=WORD)
        else:
            self.zone.config(wrap=NONE)
        self.print_line_nums()

class Searcher:

    def __init__(self):
        if docs:
            self.zone = docs[current_doc].editor.zone
            self.editor = docs[current_doc].editor

    def set_search_boundaries(self):
        selected = self.zone.tag_ranges(SEL)
        if selected: # search in selection
            self.search_pos,self.search_end = selected
        else:
            self.search_pos,self.search_end = INSERT,None
        found = self.zone.tag_ranges('found')
        if found:
            self.search_pos = found[1]

    def search(self,repl=False):
        selected = self.zone.tag_ranges(SEL)
        if selected: # tag selection (otherwise select background is lost)
            self.zone.tag_add('selection',*selected)
        self.top = Toplevel(root)
        self.top.title(_('search'))
        self.top.transient(root)
        self.top.protocol("WM_DELETE_WINDOW",self.end_search)
        self.searched = Entry(self.top,relief=GROOVE,borderwidth=4)
        self.searched.pack()
        self.searched.focus()
        if repl:
            Label(self.top,text=_('replace by')).pack()
            self.replacement = Entry(self.top,relief=GROOVE,borderwidth=4)
            self.replacement.pack()
        f_buttons = Frame(self.top)
        Checkbutton(f_buttons,text=_('full word'),
            variable=full_word).pack(anchor=W)
        Checkbutton(f_buttons,text=_('case insensitive'),
            variable=case_insensitive).pack(anchor=W)
        Checkbutton(f_buttons,text=_('regular expression'),
            variable=regular_expression).pack(anchor=W)
        f_buttons.pack(side=LEFT)
        if repl:
            Button(self.top,text=_('replace next'),
                command=self.make_replace).pack()
            Button(self.top,text=_('replace all'),
                command=self.make_replace_all).pack()
        else:
            Button(self.top,text=_('search'),
                command=self.make_search).pack()
        case_insensitive.set(False)

    def end_search(self):
        self.zone.tag_remove('selection',1.0,END)
        self.zone.tag_remove('found',1.0,END)
        self.top.destroy()

    def make_search(self):
        self.set_search_boundaries()
        pos = self.find_next()
        self.zone.tag_remove('found',1.0,END)
        if pos:
            self.zone.tag_add('found',pos,'%s+%sc' %(pos,found_length.get()))
            self.search_pos = '%s+%sc' %(pos,found_length.get())
            self.zone.see(pos)
            self.editor.print_line_nums()
        else:
            tkinter.messagebox.showinfo(title=_('search'),
                message=_('Not found'))

    def find_next(self,**kw):
        pattern = self.searched.get()
        regexp = regular_expression.get()
        if self.search_end:
            kw['stopindex'] = self.search_end
        if full_word.get():
            for car in '[](){}$^':
                pattern = pattern.replace(car,'\\'+car)
            pattern = r'(^|[^\w\d_$])%s($|[^\w\d_$])' %pattern
            regexp = True
        if case_insensitive.get():
            pattern = '(?i)'+pattern
            regexp = True
        res = self.zone.search(pattern,self.search_pos,
            count=found_length,regexp=regexp,**kw)
        ln = found_length.get()
        if res and full_word.get(): # remove borders
            try:
                line,col = [int(x) for x in res.split('.')]
            except:
                print('erreur pour res',res)
                raise
            if self.zone.get(res)!=self.searched.get()[0]:
                res = '%s.%s' %(line,col+1)
                ln -= 1
            if self.zone.get('%s+%sc' %(res,ln-1))!=self.searched.get()[-1]:
                ln -= 1
            found_length.set(ln)
        return res

    def replace(self):
        self.search(repl=True)

    def make_replace(self):
        self.set_search_boundaries()
        pos = self.find_next()
        if pos:
            self.zone.tag_remove('found',1.0,END)
            self.zone.delete(pos,'%s+%sc' %(pos,found_length.get()))
            self.zone.insert(pos,self.replacement.get())
            self.search_pos = '%s+%sc' %(pos,len(self.replacement.get()))
            self.editor.syntax_highlight()
            self.zone.tag_add('found',pos,'%s+%sc' %(pos,len(self.replacement.get())))
            self.zone.see(pos)

    def make_replace_all(self):
        self.set_search_boundaries()
        # keep undo stack separator at position before replace all
        self.zone['autoseparators'] = False
        if not self.zone.tag_ranges(SEL):
            self.search_pos = 1.0
            self.search_end = END
        found = 0
        while True:
            pos = self.find_next(stopindex=self.search_end)
            if not pos:
                break
            found += 1
            self.zone.delete(pos,'%s+%sc' %(pos,found_length.get()))
            self.zone.insert(pos,self.replacement.get())
            self.search_pos = '%s+%sc' %(pos,len(self.replacement.get()))
        if found:
            self.zone.tag_remove('found',1.0,END)
            self.editor.syntax_highlight()
            # manually add separator in undo stack
            self.zone.edit_separator()
        self.zone['autoseparator'] = True # reset to default

def search(*args):
    if docs:
        Searcher().search()

def search_in_files(*args):
    txt = tkinter.simpledialog.askstring(_('search in files'),'search')
    if txt:
        pattern = re.sub(r'([$\.()\[\]])',r'\\\1',txt)
        pattern = r'%s' %pattern
        top = Toplevel()
        zone = ScrolledText(top,width=120,height=40)
        zone.pack()
        top.title('Recherche dans les fichiers - %s' %default_dir())
        zone.insert(END,'Chaine : %s\n\n' %txt)
        for dirpath,dirnames,filenames in os.walk(default_dir()):
            flag_dir = False
            if '.hg' in dirnames:
                dirnames.remove('.hg')
            for fname in filenames:
                if fname.endswith('.gz'):
                    continue
                flag_file = False
                full_path = os.path.join(dirpath,fname)
                src = open(full_path,encoding='iso-8859-1').read()
                rest = src
                lines = src.split('\n')
                pos = 0
                while True:
                    mo = re.search(pattern,rest)
                    if mo:
                        if not flag_dir:
                            zone.insert(END,'\n\n'+dirpath)
                            flag_dir = True
                        if not flag_file:
                            zone.insert(END,'\n   %s\n' %full_path[len(default_dir())+1:]) 
                            flag_file = True
                        pos_in_src = pos + mo.start()
                        lnum = src[:pos_in_src].count('\n')
                        zone.insert(END,'\n        line %4s : %s' %(lnum+1,lines[lnum][:100]))
                        pos += mo.start()+1
                        rest = rest[mo.start()+1:]
                    else:
                        if flag_file:
                            zone.insert(END,'\n')
                        break

def replace(*args):
    if docs:
        Searcher().replace()

def save_history(doc):
    file_name = doc.file_name
    try:
        history = [line.strip()
            for line in open('history.txt').readlines()
            if line.strip() and not line.strip() == file_name]+[file_name]
    except IOError:
        out = open('history.txt','w')
        out.write(file_name+'\n')
        out.close()
        menuModule.add_separator()
        menuModule.add_command(label=file_name,
            command=lambda file_name=file_name:open_module(file_name))
        return
    out = open('history.txt','w')
    for line in history[-history_size:]:
        out.write(line+'\n')
    out.close()
    # remove entry in menu
    index = menuModule.index(END)
    deleted = False
    while index > 0:
        if menuModule.type(index) != 'command':
            break
        else:
            label = menuModule.entrycget(index,'label') #.encode('utf-8')
            if label == file_name:
                menuModule.delete(index)
                deleted = True
                break
            else:
                index -= 1
    if not deleted:
        if menuModule.index(END)>nb_menu_items+history_size:
            menuModule.delete(nb_menu_items+2) # oldest file in history
    # add to menu
    menuModule.add_command(label=file_name,
        command=lambda file_name=file_name:open_module(file_name))
    # save last modif time
    doc.last_modif = os.stat(file_name).st_mtime

def default_dir():
    if docs and docs[current_doc].has_name:
        return os.path.dirname(docs[current_doc].file_name)
    try:
        return os.path.dirname(open('history.txt').readlines()[-1])
    except IOError:
        return os.getcwd()

def run(*args):
    if not docs or not docs[current_doc].editor.zone.get(1.0,END).strip():
        return
    if docs[current_doc].file_name is None:
        save_as()
    if not docs[current_doc].file_name.endswith('.py'):
        tkinter.messagebox.showerror(title="Execution error",
            message="This is not a Python script")
        return
    save() # in case text or encoding changed
    # check if first line indicates interpreter
    first_line = docs[current_doc].editor.zone.get(1.0,'1.0lineend')
    if first_line.startswith("#!"):
        interp = first_line[2:]
    else:
        interp = dict(python_versions)[python_version.get()]
    if interp.lower().endswith("w.exe"):
        # On Windows, use python.exe, not pythonw.exe
        interp = interp[:-5] + interp[-4:]
    if ' ' in interp:
        interp = '"%s"'%interp
    if sys.platform=='win32':
        # use batch file run.bat to run script in another process
        out = open("run.bat","w")
        out.write("@echo off\ncd %1%\n{0} %2%\npause\nexit".format(interp))
        out.close()
        fname = docs[current_doc].file_name
        d_name = os.path.dirname(fname)
        d_name = d_name.replace('/','\\')
        os.system('start /D "%s" run "%s" "%s"' %(os.getcwd(),d_name,fname))
    else:   # XXX untested
        os.spawnv(os.P_NOWAIT, interp, [interp, '"'+nfich+'"'])

def switch(event):
    if not docs:
        return
    line_num = int(event.widget.index(CURRENT).split('.')[0])-1
    if not line_num in file_browser.doc_at_line:
        return
    new_index = docs.index(file_browser.doc_at_line[line_num]) 
    if new_index==current_doc:
        return
    else:
        switch_to(new_index)

def switch_to(new_index):
    global current_doc
    docs[current_doc].editor.frame.pack_forget()
    new_doc = docs[new_index]
    current_doc = new_index
    docs[current_doc].editor.frame.pack()
    root.title('TedPy - {}'.format(docs[current_doc].file_name))
    file_browser.select(new_doc)
    docs[current_doc].editor.zone.focus()
    syntax_highlight.set(docs[current_doc].editor.highlight)

def close_dialog(event):
    global current_doc
    if not docs:
        return
    line_num = int(event.widget.index(CURRENT).split('.')[0])-1
    if not line_num in file_browser.doc_at_line:
        return
    doc_index = docs.index(file_browser.doc_at_line[line_num])
    browser = Menu(root,tearoff=0,relief=FLAT,background="#DDD")
    browser.add_command(label="close",command=_close)
    browser.post(event.x_root,event.y_root)

def py_encoding(head):
    mo = re.search('(?s)coding[:=]\s*([-\w.]+)',head, re.M)
    if mo:
        return mo.groups()[0]

def html_encoding(html):
    # form <meta charset="...">
    mo = re.search('\<meta\s+charset="(.*?)"\s*/?\>',html,re.I)
    if mo:
        return mo.groups(0)[0]
    # form <meta http-equiv="content-type" type="...;charset=...">
    pattern = '\<meta\s+http-equiv\s*=\s*"content-type"\s+content\s*=\s*(.+?)".*\/?>'
    mo = re.search(pattern,html,re.I)
    if mo:
        content = mo.groups()[0]
        mo = re.search('charset\s*=\s*(.+)',content,re.I+re.S)
        if mo:
            return mo.groups()[0]

def guess_linefeed(txt):
    # guess if linefeed in text is \n, \r\n or \r
    counts = txt.count('\n'), txt.count('\r\n'), txt.count('\r')
    if counts[0]>counts[1]:
        return 'Unix: \\n'
    elif counts[2]>counts[1]:
        return 'Mac: \\r'
    return 'DOS: \\r\\n'

def set_linefeed(txt):
    """Normalise linefeed"""
    lf = linefeed.get()
    # set all linefeeds to \n
    txt = txt.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    if lf == 'Unix: \\n':
        return txt
    elif lf == 'Mac: \\r':
        return txt.replace(b'\n', b'\r')
    else:
        return txt.replace(b'\n', b'\r\n')
    
def new_module(ext):
    global current_doc
    for widget in panel.winfo_children():
        widget.pack_forget()
    editor = Editor()
    editor.frame.pack(expand=YES,fill=BOTH)
    doc = Document(None,ext)
    doc.editor = editor
    doc.editor.encoding.set(encoding_for_next_open.get())
    docs.append(doc)
    file_browser.update()
    current_doc = len(docs)-1
    file_browser.select(doc)
    editor.zone.focus()
    root.title('TedPy - {}'.format(docs[current_doc].file_name))

def open_module(file_name,force_reload=False,force_encoding=None):
    global current_doc
    file_name = os.path.normpath(file_name)
    file_encoding = None
    if not os.path.exists(file_name):
        # might happen if a file in history was removed
        tkinter.messagebox.showinfo(title=_('opening file'),
                message=_('File not found'))
        return
    if os.path.splitext(file_name)[1]=='.py':
        # search a line with encoding (see PEP 0263)
        src = open(file_name,'rb')
        try:
            head = src.readline()+src.readline()
            head = head.decode('ascii')
            file_encoding = py_encoding(head)
        except UnicodeDecodeError:
            pass
    elif os.path.splitext(file_name)[1] in ['.html','.htm']:
        # search a meta tag with charset
        if force_encoding is None:
            file_encoding = html_encoding(open(file_name,'U',errors='ignore').read())
            if not file_encoding:
                tkinter.messagebox.showwarning(title=_('HTML encoding'),
                        message=_('Charset not found'))
    if not file_encoding:
        file_encoding = encoding_for_next_open.get()
    try:
        txt = open(file_name,'r',encoding=file_encoding,newline='').read()
        txt = txt.replace('\t',' '*spaces_per_tab)
        linefeed.set(guess_linefeed(txt))
        # internally use \n, otherwise tkinter adds an extra whitespace each line
        txt = txt.replace('\r\n', '\n') 
    except UnicodeDecodeError: # try another encoding
        new_enc = EncodingChooser(_("Encoding error"),
            _("encoding_err_msg") %encoding_for_next_open.get(),
            initialvalue=encoding_for_next_open)
        if new_enc.result is not None:
            encoding_for_next_open.set(new_enc.result)
            return open_module(file_name,force_encoding=new_enc.result)
        return
    if len(docs)==1 and not docs[0].has_name \
        and not docs[0].editor.zone.get(1.0,END).strip():
            docs[0].editor.frame.pack_forget()
            del docs[0]
            file_browser.update()
            current_doc = None
    for i,doc in enumerate(docs):
        if file_name == doc.file_name:
            if not force_reload:
                tkinter.messagebox.showerror(title=_("opening_file"),
                    message=_("already_open_err_msg"))
                switch_to(i)
                file_browser.select_clear(0,END)
                file_browser.select(doc)
                return
            else:
                file_browser.delete(doc)
    editor = Editor()
    editor.zone.insert(1.0,txt)
    text = editor.zone.get(1.0,'%s-1c' %END) # returns a Unicode string
    if docs:
        docs[current_doc].editor.frame.pack_forget()
    root.title('TedPy - {}'.format(file_name))
    new_doc = Document(file_name,text=text)
    new_doc.editor = editor
    new_doc.editor.encoding.set(file_encoding)
    new_doc.last_modif = os.stat(file_name).st_mtime
    docs.append(new_doc)
    file_browser.update()
    current_doc = docs.index(new_doc)
    file_browser.select(new_doc)
    editor.zone.mark_set(INSERT,1.0)
    editor.syntax_highlight()
    editor.zone.edit_reset()
    editor.frame.pack(expand=YES,fill=BOTH)
    # wait to print lines, otherwise bbox only works for first line
    editor.zone.after(100,editor.print_line_nums)
    save_history(new_doc)
    new_doc.editor.zone.focus()

def ask_module(*args):
    file_name=askopenfilename(initialdir=default_dir())
    if file_name:
        open_module(file_name)

def check_if_changed(confirm=True):
    if docs[current_doc].editor.zone.get(1.0,'%s-1c' %END) != \
        docs[current_doc].text:
        flag = True
        if confirm:
            flag = tkinter.messagebox.askquestion("File modified",
                "File %s changed. Save it ?" %docs[current_doc].file_name)
        if flag != 'no':
            save()

def save(*args):
    if not docs:
        return
    if docs[current_doc].file_name:
        return save_zone()
    else:
        return save_as()

def save_as():
    if not docs:
        return
    file_name = asksaveasfilename(initialfile=docs[current_doc].file_name,
        initialdir=default_dir(),defaultextension=".py")
    if file_name:
        doc = docs[current_doc]
        doc.file_name = file_name
        root.title('TedPy - {}'.format(file_name))
        file_browser.delete(doc)
        file_browser.update()
        file_browser.select(doc)
        res = save_zone()
        doc.editor.syntax_highlight()
        return res

def save_zone():
    doc = docs[current_doc]
    zone = doc.editor.zone
    try:
        data = zone.get(1.0,'%s-1c' %END).encode(doc.editor.encoding.get())
    except UnicodeEncodeError as msg:
        message = "File can't be encoded with %s codec" \
            %doc.editor.encoding.get()
        start = msg.start
        text = zone.get(1.0,'%s-1c' %END)
        line = 1+text[:start].count('\n')
        if line==1:
            col = start
        else:
            col = len(text[text.rfind('\n',0,start):start])
        message += '\nInvalid character line %s, column %s' %(line,col)
        message += '\nafter '+text[start-10:start]
        tkinter.messagebox.showerror('Encoding error',
            message=message)
        return False
    # set linefeed
    data = set_linefeed(data)
    with open(doc.file_name,'wb') as out:
        out.write(data)
    doc.text = zone.get(1.0,'%s-1c' %END)
    save_history(doc)
    file_browser.mark_if_changed()
    return True

def _close(*args):
    global current_doc
    if not docs:
        return
    if docs[current_doc].editor.zone.get(1.0,'%s-1c' %END) != \
        docs[current_doc].text:
        flag = tkinter.messagebox.askquestion("File modified",
            "File %s changed. Save it ?" %docs[current_doc].file_name)
        if flag != 'no':
            if not save():
                return
    docs[current_doc].editor.frame.pack_forget()
    del docs[current_doc]
    file_browser.update()
    if docs:
        current_doc = len(docs)-1
        docs[current_doc].editor.frame.pack()
        root.title('TedPy - {}'.format(docs[current_doc].file_name))
        file_browser.select(docs[-1])
        docs[current_doc].editor.zone.focus()
    else:
        current_doc = None
        root.title('TedPy')

def close_window(*args):
    while docs:
        current_doc = -1
        _close()
    root.destroy()

def make_patterns(*args):
    # build patterns for syntax hightlight, depending on Python version
    global patterns
    se = dict(python_versions)[python_version.get()]
    if not os.path.exists(se):
        tkinter.messagebox.showerror(title="Configuration error",
            message="Python interpreter %s not found" %se)
        return
    script = 'import keyword\nout=open("_patterns.py","w")\n'
    script += 'out.write("keywords = "+str(keyword.kwlist)+"\\n")\n'
    script += 'out.write("builtins = %s" %dir(__builtins__))\nout.close()'
    out = open('build_patterns.py','w')
    out.write(script)
    out.close()
    os.system('%s "%s"' %(se,os.path.join(os.getcwd(),'build_patterns.py')))
    if not os.getcwd() in sys.path:
        sys.path.append(os.getcwd())
    import _patterns,imp
    imp.reload(_patterns)
    kw_pattern = '|'.join([ r'\b%s\b' %kw for kw in _patterns.keywords ])
    builtins_pattern = '|'.join([ r'\b%s\b' %b for b in _patterns.builtins ])
    patterns['.py'] = [(kw_pattern,'keyword'),(builtins_pattern,'builtin')]
    patterns['.py']+=[(square_brackets,'square_bracket'),
        (parenthesis,'parenthesis'),(curly_braces,'curly_brace')]
    if docs:
        docs[current_doc].editor.syntax_highlight()

def check_file_change():
    # check every second if file has been modified by another program
    if docs and docs[current_doc].has_name:
        doc = docs[current_doc]
        if os.path.exists(doc.file_name): # may have been moved or deleted
            if doc.last_modif != os.stat(doc.file_name).st_mtime:
                askreload = tkinter.messagebox.askyesno(title=_("File changed"),
                    message=_("file_change") %doc.file_name)
                if askreload:
                    _close()
                    open_module(doc.file_name)
                else:
                    doc.last_modif = os.stat(doc.file_name).st_mtime
    root.after(1000,check_file_change)

def update_highlight(*args):
    # update syntax highlighting if option is reset by user
    if docs:
        docs[current_doc].editor.syntax_highlight()
    
encoding_for_next_open = StringVar(root)
encoding_for_next_open.set('utf-8')
python_version = StringVar(root)
python_version.trace("w",make_patterns)
python_version.set(python_versions[0][0])
linefeed = StringVar(root)
target = IntVar(root)
full_word = BooleanVar(root)
full_word.set(True)
case_insensitive = BooleanVar(root)
case_insensitive.set(True)
regular_expression = BooleanVar(root)
regular_expression.set(False)
found_length = IntVar(root)
syntax_highlight = BooleanVar(root)
syntax_highlight.set(True)
syntax_highlight.trace('w', update_highlight)

menubar=Menu(root)

menuModule=Menu(menubar,tearoff=0)
menu_new = Menu(menuModule,tearoff=0)
menu_new.add_command(label=_('python'),command=lambda x='py':new_module(x))
menu_new.add_command(label=_('text'),command=lambda x='txt':new_module(x))
menuModule.add_cascade(menu=menu_new,label=_('new'))
menuModule.add_command(label=_('open'),accelerator="Ctrl+O",command=ask_module)
menuModule.add_command(label=_('save as')+"...",command=save_as)
menuModule.add_command(label=_('save'),accelerator='Ctrl+S',command=save)
menuModule.add_command(label=_('close'),command=close_window)
menuModule.add_command(label=_('run'),accelerator="Ctrl+R",command=run)
nb_menu_items = menuModule.index(END)

# history of open files
try:
    history = [ f.strip()
        for f in open('history.txt').readlines()]
    if history:
        menuModule.add_separator()
        for f in history:
            menuModule.add_command(label=f,command=lambda f=f:open_module(f))
except IOError:
    pass

menubar.add_cascade(menu=menuModule,label=_("file"))

menuEdition=Menu(menubar,tearoff=0)
menuEdition.add_command(label=_('search'),command=search,accelerator="F5")
menuEdition.add_command(label=_('search in files'),command=search_in_files,accelerator="F6")
menuEdition.add_command(label=_('replace'),command=replace,accelerator="F8")
menubar.add_cascade(menu=menuEdition,label=_('edit'))

menuConfig = Menu(menubar,tearoff=0)
menuEncoding = Menu(menuConfig,tearoff=0)
for enc in encodings:
    menuEncoding.add_radiobutton(label=enc,variable=encoding_for_next_open)
menuConfig.add_cascade(menu=menuEncoding,label=_('encoding'))

menuLinefeed = Menu(menuConfig,tearoff=0)
for lf in ['Unix: \\n', 'DOS: \\r\\n', 'Mac: \\r']:
    menuLinefeed.add_radiobutton(label = lf, variable=linefeed)
menuConfig.add_cascade(menu=menuLinefeed, label=_('linefeed'))
menuInterpreter = Menu(menuConfig,tearoff=0)
for py_ver,py_int in python_versions:
    menuInterpreter.add_radiobutton(label=py_ver,variable=python_version)
menuConfig.add_cascade(menu=menuInterpreter,label=_('Python version'))
menuConfig.add_checkbutton(label=_('highlight'),variable=syntax_highlight)
menubar.add_cascade(menu=menuConfig,label=_('config'))

root.config(menu=menubar)

root.bind('<Control-n>',new_module)
root.bind('<Control-o>',ask_module)
root.bind('<Control-s>',save)
root.bind('<Control-r>',run)
root.bind('<F5>',search)
root.bind('<F6>',search_in_files)
root.bind('<F8>',replace)
root.protocol("WM_DELETE_WINDOW",close_window)

class FileBrowser(tkinter.Text):
    # simulate a listbox : with built-in listboxes, selection 
    # disappears when a text is selected in editor

    def update(self):
        lines = [(os.path.basename(doc.file_name),doc) for doc in docs ]
        lines.sort(key=lambda x:x[0].lower())
        self.doc_line = dict((line[1],i+1) for (i,line) in enumerate(lines))
        self.doc_at_line = dict((i,line[1]) for (i,line) in enumerate(lines))
        self['state'] = NORMAL
        tkinter.Text.delete(self,1.0,END)
        for line in lines:
            tkinter.Text.insert(self,END,line[0]+'\n')
        self['state'] = DISABLED
        
    def select_clear(self,start,stop):
        self.tag_remove('selected','%s.0' %(start+1),
            '%s.0lineend' %self.index(stop).split('.')[0])

    def select(self,doc):
        self.tag_remove('selected',1.0,END)
        line = self.doc_line[doc]
        self.tag_add('selected','%s.0' %line,'%s.0lineend' %line)

    def delete(self,doc):
        line = self.doc_line[doc]
        tkinter.Text.delete(self,'%s.0' %line,'%s.0lineend' %line)

    def mark_if_changed(self):
        """Add a * after file name if modified since open or last save"""
        self['state'] = NORMAL
        doc = docs[current_doc]
        line_num = self.doc_line[doc]
        start,end = '%s.0' %line_num, '%s.0lineend' %line_num
        lib = self.get(start,end)
        if doc.editor.zone.get(1.0,END+'-1c') != doc.text:
            if not lib.endswith('*'):
                self.insert(end,'*','selected')
        elif lib.endswith('*'):
            tkinter.Text.delete(self,self.index(end)+'-1c')
        self['state'] = DISABLED


# make root cover the entire screen
root.wm_state(newstate="zoomed")
root_w, root_h = root.winfo_screenwidth(), int(root.winfo_screenheight()*0.92)

fsize = -int(root_w/120)

font = {'.py':Font(family="courier new",size=fsize,weight='bold'),
    '.js':Font(family="courier new",size=fsize,weight='bold')}
default_font = Font(family="courier new",size=fsize)
lc_font = Font(family="courier new",size=fsize)
sh_font = Font(family="courier new",size=int(1.5*fsize), weight="bold")
browser_font = Font(family="verdana",size=fsize)
curly_font = Font(family="courier new",slant='italic',size=fsize,weight="bold")

pix_per_char = font['.py'].measure('0') # pixels per character in this font
ratio = pix_per_char/font['.py']['size']
text_width = int(0.83*root_w/pix_per_char)

    
file_browser = FileBrowser(root,font=browser_font,height=38,padx=3,pady=3,
    borderwidth=6,relief=GROOVE,cursor='arrow',state=DISABLED,
    foreground='white', bg='#222222')
file_browser.tag_config('selected',foreground='#000000',background="#E0E0E0")
file_browser.pack(side=LEFT,anchor=NW,expand=YES,fill=Y)
file_browser.bind('<ButtonRelease>',switch)
file_browser.bind('<Button-3>',close_dialog)

right = Frame(root)

panel = Frame(right)
panel.pack(expand=YES,fill=BOTH)

right.pack(expand=YES,fill=BOTH)

# file browser covers 15% of width
file_browser['width'] = int(0.15*root_w/pix_per_char) 



check_file_change()

if len(sys.argv)>1:
    open_module(sys.argv[1])

root.mainloop()

