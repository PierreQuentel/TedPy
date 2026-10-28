# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import re
import time
import json
import importlib
import html.parser

from tkinter import *
from tkinter.filedialog import *
import tkinter.messagebox
import tkinter.simpledialog
import tkinter.font
from tkinter.scrolledtext import ScrolledText

import translation
translation.language = 'fr'
_ = translation.translate

this_dir = os.path.dirname(__file__)

# Load config
config_file = os.path.join(this_dir, 'texted_config.json')
with open(config_file, encoding='utf-8') as f:
    config = json.load(f)

theme = config["theme"]
with open(os.path.join(this_dir, 'themes', theme + '.json'),
        encoding='utf-8') as f:
    data = json.load(f)
    colors = data["colors"]
    backgrounds = data["backgrounds"]
    bg = backgrounds.get("default", "#fff")
    fg = colors['color']

# parameters
wheel_coeff = 2 # increase wheel scrolling
spaces_per_tab = 4

root = Tk() # needed here for font definitions
root.title("TextEd")

# global variables
current_doc = None
doc = None
wheel_delta = None
docs = []

class Fonts:
    pass


class Document:

    def __init__(self, file_name, ext=None, text=""):
        self.has_name = file_name is not None
        if file_name is None:
            # find the first available name "moduleXXX.ext"
            num = 1
            while True:
                file_name = os.path.join(default_dir(),
                    "module{}.{}".format(num, ext))
                if not os.path.exists(file_name):
                    break
                num += 1
        self.file_name = os.path.normpath(file_name)
        self.text = text
        self.ext = ext or os.path.splitext(file_name)[1][1:]

class Editor(Frame):

    def __init__(self):
        frame = Frame(panel, relief=GROOVE, borderwidth=4)

        bar_bg = colors['bar']
        self.font = Fonts.font

        shortcuts = Frame(frame, bg=bar_bg)
        for (src,callback) in [('⤶', self.undo), ('⤷', self.redo)]:
            widget = Label(shortcuts, text=src, relief=RIDGE, bg='#FFF',
                foreground='#000', font=Fonts.sh)
            widget['width'] = 2
            widget.bind('<Button-1>', callback)
            widget.pack(side=LEFT, anchor=W)

        w_italic = Label(shortcuts, text='I', relief=RIDGE, bg='#FFF',
                foreground='#000', font=Fonts.menu_italic)
        w_italic['width'] = 2
        w_italic.bind('<Button-1>', self.italic)
        w_italic.pack(side=LEFT, anchor=W)

        self.special_box = False

        widget = Button(shortcuts, text='X', font=Fonts.sh, relief=RIDGE)
        widget.bind('<Button-1>', _close)
        widget.pack(side=RIGHT, anchor=E)
        Label(shortcuts, text='    ', bg=bar_bg).pack(side=RIGHT)
        self.label_line = Label(shortcuts, font=Fonts.font, fg=fg, bg=bar_bg)
        self.label_column = Label(shortcuts, font=Fonts.font, fg=fg, bg=bar_bg)
        self.label_column.pack(side=RIGHT)
        Label(shortcuts, text=' | ', bg=bar_bg, fg=fg).pack(side=RIGHT)
        self.label_line.pack(side=RIGHT)

        shortcuts.pack(fill=BOTH)

        zone = ScrolledText(frame, width=self.text_width(),
            font=Fonts.font, wrap=WORD, relief=FLAT, undo=True,
            autoseparators=True, bg=bg, fg=fg, selectforeground=fg,
            insertbackground=fg, selectbackground=colors['select'])
        line_height = zone.dlineinfo(1.0)[-1] # in pixels
        text_height = int(int(root.winfo_screenheight() * 0.92) / line_height)
        zone['height'] = text_height

        hbar = Scrollbar(frame, name='hbar', orient=HORIZONTAL)
        hbar.pack(side=BOTTOM, fill=BOTH, expand=YES)
        hbar['command'] = zone.xview
        zone['xscrollcommand'] = hbar.set

        zone.bind('<KeyRelease>', self.update)
        zone.bind('<Button-1>', self.click)
        zone.bind('<ButtonRelease-1>', self.button_release)
        zone.bind('<Control-i>', self.italic)

        zone.tag_config('found', foreground=bg, background=fg)
        zone.tag_config('selection', background=zone['selectbackground'],
            borderwidth=0)
        zone.tag_config('italic', foreground=fg, background=bg,
            font=Fonts.italic)

        zone.tag_raise(SEL, 'italic')

        zone.pack(expand=YES, fill=BOTH)

        self.zone = zone
        self.frame = frame
        self.shift = False

    def button_release(self, event):
        self.zone['cursor'] = 'xterm'
        self.update_line_col()

    def click(self,event):
        global close_menu
        self.zone.tag_remove('selection', 1.0, END)
        self.zone.tag_remove('found', 1.0, END)
        if close_menu is not None:
            close_menu.unpost()
            close_menu = None

    def insert_special(self, event):
        if self.zone.tag_ranges(SEL):
            self.zone.delete(*self.zone.tag_ranges(SEL))
        self.zone.insert(INSERT, event.widget.cget('text'))
        self.special_box.destroy()
        self.special_box = False

    def italic(self, event):
        sel = self.zone.tag_ranges(SEL)
        if sel:
            names = self.zone.tag_names(sel[0])
            if 'italic' not in names:
                self.zone.tag_add('italic', *sel)
            else:
                self.zone.tag_remove('italic', *sel)
        return 'break'
        
    def ix2pos(self, ix):
        return [int(x) for x in self.zone.index(ix).split('.')]

    def redo(self,*args):
        try:
            self.zone.edit_redo()
        except:
            pass

    def text_width(self):
        pix_per_char = Fonts.font.measure('0') # pixels per char in this font
        return int(root.winfo_screenwidth() / pix_per_char)

    def undo(self, *args):
        try:
            self.zone.edit_undo()
        except:
            pass

    def update(self, event):
        self.update_line_col()
        self.zone.see(INSERT)
        if self.shift:
            if event.keysym in ['Shift_R', 'Shift_L']:
                self.shift = False
            if not event.char or \
                    (hasattr(event.char, 'string') and not event.char.string):
                return

    def update_line_col(self, *args):
        self.current_line, column = map(int,
            self.zone.index(INSERT).split('.'))
        self.label_line['text'] = "{: 5d}".format(self.current_line)
        self.label_column['text'] = "{: 3d}".format(column + 1)


class Searcher:
    """Class for search dialogs."""

    def editor(self):
        return doc.editor

    def zone(self):
        return doc.editor.zone

    def set_search_boundaries(self):
        selected = self.zone().tag_ranges(SEL)
        if selected: # search in selection
            self.search_pos, self.search_end = selected
        else: # search in whole document
            self.search_pos, self.search_end = INSERT, None
        found = self.zone().tag_ranges('found')
        if found:
            self.search_pos = found[1]

    def search(self, repl=False):
        selected = self.zone().tag_ranges(SEL)
        if selected: # tag selection (otherwise select background is lost)
            self.zone().tag_add('selection', *selected)
        self.top = Toplevel(root)
        root.search = self.top
        self.top.title(_('search'))
        self.top.transient(root)
        self.top.protocol('WM_DELETE_WINDOW', self.end_search)
        self.searched = Entry(self.top, relief=GROOVE, borderwidth=4)
        self.searched.pack()
        self.searched.focus()
        if repl:
            Label(self.top, text=_('replace by')).pack()
            self.replacement = Entry(self.top, relief=GROOVE, borderwidth=4)
            self.replacement.pack()
        f_buttons = Frame(self.top)
        Checkbutton(f_buttons, text=_('full word'),
            variable=full_word).pack(anchor=W)
        Checkbutton(f_buttons, text=_('case insensitive'),
            variable=case_insensitive).pack(anchor=W)
        f_buttons.pack(side=LEFT)
        if repl:
            Button(self.top, text=_('replace next'),
                command=self.make_replace).pack()
            Button(self.top, text=_('replace all'),
                command=self.make_replace_all).pack()
        else:
            Button(self.top, text=_('search'),
                command=self.make_search).pack()
        case_insensitive.set(False)

    def end_search(self):
        self.zone().tag_remove('selection', 1.0, END)
        self.zone().tag_remove('found', 1.0, END)
        self.top.destroy()

    def make_search(self):
        self.set_search_boundaries()
        pos = self.find_next()
        self.zone().tag_remove('found', 1.0, END)
        if pos:
            self.zone().tag_add('found', pos,
                '{}+{}c'.format(pos,found_length.get()))
            self.search_pos = '{}+{}c'.format(pos, found_length.get())
            self.zone().see(pos)
        else:
            tkinter.messagebox.showinfo(title=_('search'),
                message=_('Not found'))

    def find_next(self, **kw):
        pattern = self.searched.get()
        if self.search_end:
            kw['stopindex'] = self.search_end
        if full_word.get():
            for car in '[](){}$^.':
                pattern = pattern.replace(car, '\\'+car)
            pattern = r'\m{}\M'.format(pattern)
        if case_insensitive.get():
            pattern = '(?i)' + pattern
        res = self.zone().search(pattern, self.search_pos,
            count=found_length, regexp=True, **kw)
        ln = found_length.get()
        if res and full_word.get(): # remove borders
            line, col = [int(x) for x in res.split('.')]
            if self.zone().get(res) != self.searched.get()[0]:
                res = '{}.{}'.format(line, col + 1)
                ln -= 1
            if self.zone().get('{}+{}c'.format(res, ln - 1)) != \
                    self.searched.get()[-1]:
                ln -= 1
            found_length.set(ln)
        return res

    def replace(self):
        self.search(repl=True)

    def make_replace(self):
        self.set_search_boundaries()
        pos = self.find_next()
        if pos:
            zone = self.zone()
            zone.tag_remove('found', 1.0, END)
            end_pos = '{}+{}c'.format(pos, found_length.get())
            found = zone.get(pos, end_pos)
            zone.delete(pos, end_pos)
            if regular_expression.get():
                repl = re.sub(self.searched.get(), self.replacement.get(),
                    found)
            else:
                repl = self.replacement.get()
            zone.insert(pos, repl)
            self.search_pos = '{}+{}c'.format(pos, len(repl))
            self.editor().syntax_highlight()
            zone.tag_add('found', pos, '{}+{}c'.format(pos, len(repl)))
            zone.see(pos)

    def make_replace_all(self):
        self.set_search_boundaries()
        # keep undo stack separator at position before replace all
        zone = self.zone()
        zone['autoseparators'] = False
        if not zone.tag_ranges(SEL):
            self.search_pos = 1.0
            self.search_end = END
        found = 0
        while True:
            pos = self.find_next(stopindex=self.search_end)
            if not pos:
                break
            found += 1
            zone.delete(pos,'{}+{}c'.format(pos, found_length.get()))
            zone.insert(pos,self.replacement.get())
            self.search_pos = '{}+{}c'.format(pos,
                len(self.replacement.get()))
        if found:
            zone.tag_remove('found', 1.0, END)
            self.editor().syntax_highlight()
            # manually add separator in undo stack
            zone.edit_separator()
        zone['autoseparator'] = True # reset to default

def ask_module(*args):
    file_name = askopenfilename(initialdir=default_dir())
    if file_name:
        open_module(file_name)

def check_file_change():
    # check every second if file has been modified by another program
    if docs and docs[current_doc].has_name:
        doc = docs[current_doc]
        if os.path.exists(doc.file_name): # may have been moved or deleted
            if doc.last_modif != os.stat(doc.file_name).st_mtime:
                askreload = tkinter.messagebox.askyesno(
                    title=_("File changed"),
                    message=_("file_change").format(doc.file_name))
                if askreload:
                    _close()
                    open_module(doc.file_name)
                else:
                    doc.last_modif = os.stat(doc.file_name).st_mtime
    root.after(1000, check_file_change)

def _close(*args):
    global doc
    if doc is None:
        return
    if (doc.editor.zone.get(1.0, '{}-1c'.format(END)) !=
            doc.text):
        flag = tkinter.messagebox.askquestion("File modified",
            "File {} changed. Save it ?".format(doc.file_name))
        if flag != 'no' and not save():
            return
    doc.editor.frame.pack_forget()
    root.title('TextEd')

close_menu = None

def close_window(*args):
    _close()
    root.destroy()

def default_dir():
    return os.getcwd()

def new_module():
    ext = 'bzh'
    global doc
    if doc is not None:
        _close()
    for widget in panel.winfo_children():
        widget.pack_forget()
    editor = Editor()
    editor.frame.pack(expand=YES, fill=BOTH)
    doc = Document(None, ext)
    doc.editor = editor
    editor.zone.focus()
    root.title('TedPy - {}'.format(doc.file_name))

def open_module(file_name, force_reload=False, force_encoding=None):
    global doc
    if doc is not None:
        _close()
    file_name = os.path.normpath(file_name)
    file_encoding = None
    if not os.path.exists(file_name):
        # might happen if a file in history was removed
        tkinter.messagebox.showinfo(title=_('opening file'),
                message=_('File not found'))
        return
    extension = os.path.splitext(file_name)[1]
    if extension != '.bzh':
        tkinter.messagebox.showinfo(title=_('opening file'),
                message=_('Wrong extension'))
        return
    file_encoding = 'utf-8'
    with open(file_name, 'r', encoding=file_encoding) as f:
        data = json.load(f)
    txt = data['text']
    txt = txt.replace('\t', ' ' * spaces_per_tab)
    # internally use \n, otherwise tkinter adds an extra whitespace
    # for each line
    txt = txt.replace('\r\n', '\n')

    editor = Editor()
    editor.zone.insert(1.0, txt)
    text = editor.zone.get(1.0, '{}-1c'.format(END))
    root.title('TextEd - {}'.format(file_name))
    doc = Document(file_name, text=text)
    doc.editor = editor
    doc.last_modif = os.stat(file_name).st_mtime
    for tag_name in data['tags']:
        marks = data['tags'][tag_name]
        for i in range(0, len(marks), 2):
            x1, x2 = marks[i]
            y1, y2 = marks[i + 1]
            editor.zone.tag_add(tag_name, f'{x1}.{x2}', f'{y1}.{y2}')

    editor.zone.mark_set(INSERT, 1.0)
    editor.update_line_col()
    editor.zone.edit_reset()
    editor.frame.pack(expand=YES, fill=BOTH)
    doc.editor.zone.focus()

def replace(*args):
    if doc is not None:
        Searcher().replace()

def save(*args):
    if doc is None:
        return
    if doc.file_name:
        return save_zone()
    else:
        return save_as()

def save_as():
    if doc is None:
        return
    file_name = asksaveasfilename(
        initialfile=os.path.basename(docs[current_doc].file_name),
        initialdir=default_dir())
    if file_name:
        doc.file_name = os.path.normpath(file_name)
        root.title('TextEd - {}'.format(file_name))
        res = save_zone()
        return res

def save_zone():
    zone = doc.editor.zone
    text = zone.get(1.0, '{}-1c'.format(END))
    data = {'text': text, 'tags': {}}
    for tag in zone.tag_names():
        if tag in ['sel', 'selection']:
            continue
        ranges = list(map(doc.editor.ix2pos, zone.tag_ranges(tag)))
        data['tags'][tag] = ranges

    with open(doc.file_name, 'w') as out:
        json.dump(data, out)

    doc.text = zone.get(1.0, '{}-1c'.format(END))
    return True

def search(*args):
    if doc is not None:
        Searcher().search()

def set_fonts():
    root_w = root.winfo_screenwidth()
    fsize = config.get("font-size", -int(root_w / 90))

    families = tkinter.font.families(root)
    if "Consolas" in families:
        family = "Consolas"
    else:
        family = "Courier New"
    Fonts.font = tkinter.font.Font(family=family, size=fsize)
    Fonts.bold = tkinter.font.Font(family=family, size=fsize,
        weight="bold")
    Fonts.italic = tkinter.font.Font(family=family, size=fsize,
        slant="italic")
    Fonts.sh = tkinter.font.Font(family=family, size=int(1.5 * fsize),
        weight="bold")
    Fonts.menu_italic = tkinter.font.Font(family=family,
        size=int(1.5 * fsize),
        slant="italic")
    Fonts.bold_italic = tkinter.font.Font(family=family,
        size=int(1.5 * fsize),
        weight="bold", slant="italic")

def set_sizes():
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    ratio = w / Fonts.font.measure('0')

full_word = BooleanVar(root)
full_word.set(True)
case_insensitive = BooleanVar(root)
case_insensitive.set(True)
found_length = IntVar(root)

menubar=Menu(root)

menuModule=Menu(menubar, tearoff=0)
menu_new = Menu(menuModule, tearoff=0)
menuModule.add_command(label=_('new'), accelerator='Ctrl+N', command=new_module)
menuModule.add_command(label=_('open'), accelerator='Ctrl+O',
    command=ask_module)
menuModule.add_command(label=_('save as') + '...', command=save_as)
menuModule.add_command(label=_('save'), accelerator='Ctrl+S', command=save)
menuModule.add_command(label=_('close'), command=close_window)
nb_menu_items = menuModule.index(END)

menubar.add_cascade(menu=menuModule, label=_('file'))

menuEdition=Menu(menubar, tearoff=0)
menuEdition.add_command(label=_('search'), command=search, accelerator="F5")
menuEdition.add_command(label=_('replace'), command=replace, accelerator="F8")
menubar.add_cascade(menu=menuEdition, label=_('edit'))

root.config(menu=menubar)

root.bind('<Control-n>', new_module)
root.bind('<Control-o>', ask_module)
root.bind('<Control-s>', save)
root.bind('<F5>', search)
root.bind('<F8>', replace)
root.protocol('WM_DELETE_WINDOW', close_window)

set_fonts()

root.geometry('{}x{}'.format(
    int(0.4 * root.winfo_screenwidth()),
    int(0.4 * root.winfo_screenheight())))

set_sizes()

right = Frame(root)

panel = Frame(right)
panel.pack(expand=YES, fill=BOTH)
right.pack(expand=YES, fill=BOTH)

check_file_change()

if len(sys.argv) > 1:
    open_module(sys.argv[1])

root.mainloop()
