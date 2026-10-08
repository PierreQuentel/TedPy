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
        self.font = font

        shortcuts = Frame(frame, bg=bar_bg)
        for (src,callback) in [('⤶', self.undo), ('⤷', self.redo),
                ('≡', self.change_wrap), ('↑', self.change_size),
                ('↓', self.change_size)]:
            widget = Label(shortcuts, text=src, relief=RIDGE, bg='#FFF',
                foreground='#000', font=sh_font)
            widget['width'] = 2
            widget.bind('<Button-1>', callback)
            widget.pack(side=LEFT, anchor=W)

        self.special_box = False

        widget = Button(shortcuts, text='X', font=sh_font, relief=RIDGE)
        widget.bind('<Button-1>', _close)
        widget.pack(side=RIGHT, anchor=E)
        Label(shortcuts, text='    ', bg=bar_bg).pack(side=RIGHT)
        self.label_line = Label(shortcuts, font=font, fg=fg, bg=bar_bg)
        self.label_column = Label(shortcuts, font=font, fg=fg, bg=bar_bg)
        self.label_column.pack(side=RIGHT)
        Label(shortcuts, text=' | ', bg=bar_bg, fg=fg).pack(side=RIGHT)
        self.label_line.pack(side=RIGHT)

        shortcuts.pack(fill=BOTH)

        zone = ScrolledText(frame, width=self.text_width(),
            font=font, wrap=WORD, relief=FLAT, undo=True,
            autoseparators=True, bg=bg, fg=fg, selectforeground=fg,
            insertbackground=fg, selectbackground=colors['select'])
        zone.vbar.config(command=self.slide)
        line_height = zone.dlineinfo(1.0)[-1] # in pixels
        text_height = int(int(root.winfo_screenheight() * 0.92) / line_height)
        zone['height'] = text_height

        hbar = Scrollbar(frame, name='hbar', orient=HORIZONTAL)
        hbar.pack(side=BOTTOM, fill=BOTH, expand=YES)
        hbar['command'] = zone.xview
        zone['xscrollcommand'] = hbar.set

        zone.bind('<Key>', self.key_pressed)
        zone.bind('<KeyRelease>', self.update)
        zone.bind('<MouseWheel>', self.wheel)
        zone.bind('<Button-4>', self.wheel2) # wheel up
        zone.bind('<Button-5>', self.wheel2) # wheel down
        zone.bind('<Tab>', self.insert_tab)
        zone.bind('<Shift-Tab>', self.remove_tab)
        zone.bind('<Return>', self.insert_cr)
        zone.bind('<Button-1>', self.click)
        zone.bind('<ButtonRelease-1>', self.button_release)
        zone.bind('<Control-KeyRelease-v>', self.paste)
        zone.bind('<Control-Key>', self.set_control)
        zone.bind('<Home>', self.home)

        zone.tag_config('found', foreground=bg, background=fg)
        zone.tag_config('selection', background=zone['selectbackground'],
            borderwidth=0)
        zone.tag_config('italic', foreground=fg, background=bg,
            font=italic_font)

        zone.pack(expand=YES, fill=BOTH)

        self.zone = zone
        self.scripts = []
        self.frame = frame
        self.shift = False
        self.control = False
        self.last_update = None
        self.last_highlight_time = 0.5

    def button_release(self, event):
        self.zone['cursor'] = 'xterm'
        self.update_line_col()

    def change_encoding(self):
        new_enc = self.encoding.get()
        # Check that the document can be encoded in the new encoding
        src = self.zone.get(1.0, END)
        try:
            src.encode(new_enc)
        except:
            tkinter.messagebox.showinfo(title=_('Encoding error'),
                message=_('not encoding').format(self.prev_enc))

    def change_size(self, ev):
        """Called when clicking on button ↑ or ↓"""
        up = ev.widget.cget('text') == '↑'
        for f in [font, sh_font]:
            previous = f.cget('size')
            if up:
                f.config(size=previous - 1)
            else:
                f.config(size=previous + 1)
        # update config
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        data["font-size"] = font["size"]
        with open(config_file, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=4)
        set_sizes()

    def change_wrap(self,*args):
        if self.zone['wrap'] == NONE:
            self.zone.config(wrap=WORD)
        else:
            self.zone.config(wrap=NONE)

    def click(self,event):
        global close_menu
        self.zone.tag_remove('selection', 1.0, END)
        self.zone.tag_remove('found', 1.0, END)
        if close_menu is not None:
            close_menu.unpost()
            close_menu = None

    def get_extension(self):
        return os.path.splitext(docs[current_doc].file_name)[1]

    def get_infos(self, pos):
        ext = self.get_extension()
        pos = self.zone.index(pos)
        if ext == '.html':
            self.html_highlight() # reset self.scripts
            if "script_in_html" in self.zone.tag_names(pos):
                for (lang, begin, end) in self.scripts:
                    if float(begin) <= float(pos) <= float(end):
                        return lang, begin, end
        lang = ext2lang.get(ext)
        return lang, "1.0", END

    def get_visible_text(self):
        """Inspired by https://stackoverflow.com/questions/76691615"""
        widget = self.zone
        y = widget.winfo_height()
        bd = int(widget.cget("borderwidth"))
        start_index = int(widget.index(f"@0,{bd} linestart").split('.')[0])
        end_index = int(widget.index(f"@0,{y} linestart").split('.')[0])
        if widget.bbox(f'{end_index + 1}.0') is not None:
            end_index += 1
        return start_index, end_index

    def goto(self, evt):
        browser_line = int(evt.widget.index(CURRENT).split('.')[0])
        line_num = self.function_line_nums[browser_line - 1]
        self.browser.destroy()
        self.zone.focus()
        self.zone.mark_set(INSERT, '{}.0'.format(line_num))
        self.zone.see(INSERT)

    def home(self,event):
        """Home key : go to start of line, after the indentation"""
        left = self.zone.get('{}linestart'.format(self.zone.index(INSERT)),
            INSERT)
        if not left.strip(): # only spaces at the left of INSERT
            return
        nbspaces = len(left) - len(left.lstrip())
        self.zone.mark_set(INSERT, '{}linestart+{}c'.format(
             self.zone.index(INSERT), nbspaces))
        return 'break'

    def html_highlight(self):
        txt = self.zone.get(1.0, END).rstrip() + '\n'
        parser = HTMLParser(self)
        # while editing there may be parser error, ignore them
        try:
            parser.feed(txt)
            self.scripts = parser.scripts
        except Exception as exc:
            pass

    def insert_cr(self,event):
        """Handle Enter key"""
        selected = self.zone.tag_ranges(SEL)
        if selected: # remove selection
            start,end = selected
            self.zone.delete(*selected)
            if self.zone.index(end).endswith('.0'):
                self.zone.delete(start)

        pos = self.zone.index(INSERT)
        start = self.zone.index('{}linestart'.format(pos))
        txt = self.zone.get(start, pos)
        indent = len(txt) - len(txt.lstrip())

        self.remove_trailing_whitespace()

        # For a Python script, if line ends with ':', add indent
        # Same for a JS files if line ends with '{'
        lang, begin, end = self.get_infos(INSERT)
        self.zone.insert(INSERT, '\n' + indent * ' ')
        if lang in langs:
            lineend = getattr(langs[lang], "autoindent_lineend", None)
            if lineend is not None and txt.strip().endswith(lineend):
                self.zone.insert(INSERT, spaces_per_tab * ' ')

        return 'break'

    def insert_special(self, event):
        if self.zone.tag_ranges(SEL):
            self.zone.delete(*self.zone.tag_ranges(SEL))
        self.zone.insert(INSERT, event.widget.cget('text'))
        self.special_box.destroy()
        self.special_box = False

    def insert_tab(self,event):
        """Replace tabs by a number of spaces"""
        sel = self.zone.tag_ranges(SEL)
        if not sel:
            self.zone.insert(INSERT, ' ' * spaces_per_tab)
        else:
            first_line,last_line = [int(self.zone.index(x).split('.')[0])
                for x in sel]
            if self.zone.index(sel[1]).endswith('.0'):
                last_line -= 1
            for line in range(first_line, last_line + 1):
                self.zone.insert(float(line), ' ' * spaces_per_tab)
        return 'break'

    def ix2pos(self, ix):
        return [int(x) for x in self.zone.index(ix).split('.')]

    def key_pressed(self,event):
        self.delete_end = False
        if event.keysym in ['Shift_R', 'Shift_L']:
            self.shift = True
        elif event.keysym in ['Control_L', 'Control_R']:
            self.control = True
        elif event.keysym == 'Delete':
            # if delete at the end of a line, remove trailing whitespaces
            # of next line
            pos = self.ix2pos(INSERT)
            lineend = self.ix2pos('{}.0'.format(pos[0]) + 'lineend')[1]
            if pos[1] == lineend:
                self.delete_end = True

    def mark_brace(self, pos):
        if not syntax_highlight.get():
            return

        ext = self.get_extension()
        if not ext in ['.py', '.js']:
            return
        self.zone.tag_remove('matching_brace', '1.0', END)

        for p in pos + '-1c', pos, pos + '+1c':
            px = self.zone.index(p)
            if 'string' in self.zone.tag_names(px):
                return
            car = self.zone.get(px)
            if car in '([{':
                # opening brace : look for closing (after)
                match, start, nb = ')]}'['([{'.index(car)], px, 1
                incr, backwards, end_pos = "+1c", False, END
                break
            elif p in [pos, pos + "-1c"] and car in '}])':
                if p == pos + "-1c" and self.zone.get(pos) in '([{}])':
                    continue
                # closing brace : look for opening (before)
                match, start, nb = '([{'[')]}'.index(car)], px, 1
                incr, backwards, end_pos = "-1c", True, '1.0'
                break
        else:
            return

        pattern = '[\\' + car + '\\' + match + ']'
        p = start
        while True:
            next_pos = self.zone.index(p + incr)
            if backwards and re.match(pattern, self.zone.get(next_pos)):
                p = next_pos
            else:
                p = self.zone.search(pattern, next_pos, end_pos,
                    regexp=True, backwards=backwards)
            if not p:
                break
            elif 'string' in self.zone.tag_names(p):
                continue
            else:
                c = self.zone.get(p)
                if c == car:
                    nb += 1
                elif c == match:
                    nb -= 1
                    if nb == 0:
                        self.zone.tag_add('matching_brace', start)
                        self.zone.tag_add('matching_brace', p)
                        return

    def paste(self, event):
        return 'break'

    def redo(self,*args):
        try:
            self.zone.edit_redo()
        except:
            pass

    def remove_functions_browser(self):
        if hasattr(self, "browser"):
            self.browser.destroy()
            delattr(self, "browser")
            self.zone.tag_remove('word', 1.0, END)

    def remove_tab(self,event):
        """Shift selected zone to the left by the number of spaces specified
        in spaces_per_tab
        """
        sel = self.zone.tag_ranges(SEL)
        if not sel:
            nb = spaces_per_tab
            while nb and self.zone.get(INSERT) == ' ':
                self.zone.delete(INSERT)
                nb -= 1
        else:
            first_line,last_line = [int(self.zone.index(x).split('.')[0])
                for x in sel]
            if self.zone.index(sel[1]).endswith('.0'):
                last_line -= 1
            for line in range(first_line, last_line + 1):
                nb = spaces_per_tab
                while nb and self.zone.get(float(line)) == ' ':
                    self.zone.delete(float(line))
                    nb -= 1
        return 'break'

    def remove_trailing_whitespace(self):
        """Removes trailing whitespaces."""
        last_line = self.ix2pos(END)[0]
        for i in range(1, last_line + 1):
            line = self.zone.get('{}.0linestart'.format(i),
                '{}.0lineend'.format(i))
            rstripped = line.rstrip()
            if rstripped != line:
                self.zone.delete('{}.{}'.format(i, len(rstripped)),
                    '{}.0lineend'.format(i))

    def set_control(self,event):
        self.control = True

    def show_special(self, event):
        if self.special_box:
            self.special_box.destroy()
            self.special_box = False
        else:
            self.special_box = Toplevel()
            for car in 'áíóú':
                w = Label(self.special_box, text=car, relief=RIDGE,
                    font=sh_font)
                w.pack(side=LEFT, anchor=W)
                w.bind('<Button-1>', self.insert_special)
            h = int(1.1 * abs(sh_font['size']))
            self.special_box.geometry(f'1x{h}+{event.x_root}+{event.y_root}')

    def slide(self, *args):
        self.zone.yview(*args)

    def text_width(self):
        pix_per_char = font.measure('0') # pixels per char in this font
        return int(0.85 * root.winfo_screenwidth() / pix_per_char)

    def undo(self, *args):
        try:
            self.zone.edit_undo()
        except:
            pass

    def update(self, event):
        if event.keysym == 'Tab':
            return 'break'
        if self.control:
            self.control = False
            return 'break'
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

    def wheel(self,event):
        """Mouse wheel for systems where events are Button-4 and Button-5."""
        global wheel_delta
        if event.delta != 0:
            if wheel_delta is None or abs(event.delta) < wheel_delta:
                wheel_delta = abs(event.delta) / wheel_coeff
            delta = -event.delta / wheel_delta
            self.slide('scroll', int(delta), 'units')
        return "break" # don't propagate

    def wheel2(self, event):
        delta = -1 if event.num == 4 else 1
        self.slide('scroll', delta, 'units')

class Searcher:
    """Class for search dialogs."""

    def editor(self):
        return docs[current_doc].editor

    def zone(self):
        return docs[current_doc].editor.zone

    def set_search_boundaries(self):
        selected = self.zone().tag_ranges(SEL)
        if selected: # search in selection
            self.search_pos, self.search_end = selected
        else: # search in whole document
            self.search_pos, self.search_end = INSERT, None
        found = self.zone().tag_ranges('found')
        if found:
            self.search_pos = found[1]

    def search(self, repl=False, files=False):
        selected = self.zone().tag_ranges(SEL)
        if selected: # tag selection (otherwise select background is lost)
            self.zone().tag_add('selection', *selected)
        self.top = Toplevel(root)
        root.search = self.top
        self.top.title(_('search' if not files else 'search in files'))
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
        if not files:
            Checkbutton(f_buttons, text=_('regular expression'),
                variable=regular_expression).pack(anchor=W)
        f_buttons.pack(side=LEFT)
        if files:
            ext = Frame(f_buttons)
            Label(ext, text=_('extensions')).pack(anchor=W)
            self.extensions = Entry(ext)
            self.extensions.insert(INSERT, docs[current_doc].ext)
            self.extensions.pack()
            ext.pack(side=BOTTOM, pady=5)
        if repl:
            Button(self.top, text=_('replace next'),
                command=self.make_replace).pack()
            Button(self.top, text=_('replace all'),
                command=self.make_replace_all).pack()
        elif files:
            Button(self.top, text=_('search'),
                command=self.make_search_files).pack()
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

    def open_file(self, event):
        zone = event.widget
        file_name, line = zone.links[zone.tag_prevrange('link', CURRENT)]
        for ix, doc in enumerate(docs):
            if doc.file_name == file_name:
                docs[current_doc].editor.remove_functions_browser()
                switch_to(ix)
                break
        else:
            # not found, open file
            open_module(file_name)
        ed = docs[current_doc].editor
        ed.zone.focus()
        ed.zone.mark_set(INSERT, '{}.0'.format(line + 1))
        ed.zone.see(INSERT)

    def make_search_files(self):
        txt = self.searched.get()
        pattern = txt
        if full_word.get():
            for car in '[](){}$^.':
                pattern = pattern.replace(car, '\\'+car)
            pattern = r'(^|[^\w\d_$]){}($|[^\w\d_$])'.format(pattern)
        flags = 0
        if case_insensitive.get():
            flags = re.I
        extensions = [x.strip() for x in self.extensions.get().split()]
        extensions = [x if x.startswith('.') else '.' + x for x in extensions]
        top = Toplevel()
        zone = ScrolledText(top, width=120, height=40)
        zone.links = {}
        zone.pack()
        zone.tag_config('link', foreground="blue", underline=1)
        zone.tag_bind('link', '<Button-1>', self.open_file)
        zone.tag_bind('link', "<Enter>", lambda *args: zone.config(cursor="hand1"))
        zone.tag_bind('link', "<Leave>", lambda *args: zone.config(cursor=""))
        top.title(_('search_in_files').format(default_dir()))
        zone.insert(END, _('string').format(txt))
        for dirpath, dirnames, filenames in os.walk(default_dir()):
            flag_dir = False
            if '.hg' in dirnames:
                dirnames.remove('.hg')
            for fname in filenames:
                if extensions and os.path.splitext(fname)[1] not in extensions:
                    continue
                if fname.endswith(('.gz', '.zip')):
                    continue
                flag_file = False
                full_path = os.path.join(dirpath, fname)
                src = open(full_path, encoding='iso-8859-1').read()
                rest = src
                lines = src.split('\n')
                pos = 0
                save_lnum = None
                while True:
                    try:
                        mo = re.search(pattern, rest, flags=flags)
                    except:
                        print('error with pattern', pattern)
                        raise
                    if mo:
                        if not flag_dir:
                            zone.insert(END,'\n\n' + dirpath)
                            flag_dir = True
                        if not flag_file:
                            zone.insert(END, '\n   {}\n'.format(
                                full_path[len(default_dir()) + 1:]))
                            flag_file = True
                        pos_in_src = pos + mo.start()
                        while src[pos_in_src] == '\n':
                            pos_in_src += 1
                        lnum = src[:pos_in_src].count('\n')
                        if lnum != save_lnum:
                            zone.insert(END, '\n        ')
                            zone.insert(END, 'line %4s' %(lnum+1), "link")
                            zone.links[zone.tag_prevrange('link', CURRENT)] = (
                                full_path, lnum)
                            zone.insert(END, ' : %s'
                                %(lines[lnum][:100]))
                            save_lnum = lnum
                        pos += mo.start() + len(txt)
                        rest = rest[mo.start() + len(txt):]
                    else:
                        if flag_file:
                            zone.insert(END, '\n')
                        break

    def find_next(self, **kw):
        pattern = self.searched.get()
        regexp = regular_expression.get()
        if self.search_end:
            kw['stopindex'] = self.search_end
        if full_word.get():
            for car in '[](){}$^.':
                pattern = pattern.replace(car, '\\'+car)
            pattern = r'(^|[^\w\d_$]){}($|[^\w\d_$])'.format(pattern)
            regexp = True
        if case_insensitive.get():
            pattern = '(?i)' + pattern
            regexp = True
        res = self.zone().search(pattern, self.search_pos,
            count=found_length, regexp=regexp, **kw)
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

    def search_in_files(self):
        self.search(files=True)

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

def close_dialog(event):
    global current_doc, close_menu
    if not docs:
        return
    line_num = int(event.widget.index(CURRENT).split('.')[0]) - 1
    if not line_num in file_browser.doc_at_line:
        return
    doc_index = docs.index(file_browser.doc_at_line[line_num])
    current_doc = doc_index
    new_doc = docs[doc_index]
    file_browser.select(new_doc)
    close_menu = Menu(root, tearoff=0, relief=FLAT, background='#ddd')
    close_menu.add_command(label=_('close'), command=_close)
    close_menu.post(event.x_root, event.y_root - 10)

def close_window(*args):
    while docs:
        current_doc = -1
        _close()
    root.destroy()

def default_dir():
    return os.getcwd()

def guess_linefeed(txt):
    # guess if linefeed in text is \n, \r\n or \r
    counts = txt.count('\n'), txt.count('\r\n'), txt.count('\r')
    if counts[0] > counts[1]:
        return 'Unix: \\n'
    elif counts[2] > counts[1]:
        return 'Mac: \\r'
    return 'DOS: \\r\\n'

def html_encoding(html):
    # form <meta charset="...">
    mo = re.search(r'<meta\s+charset="(.*?)"\s*/?>', html, re.I)
    if mo:
        return mo.groups(0)[0]
    # form <meta http-equiv="content-type" type="...;charset=...">
    pattern = r'<meta\s+http-equiv\s*=\s*"content-type"\s+content\s*=\s*(.+?)".*/?>'
    mo = re.search(pattern, html, re.I)
    if mo:
        content = mo.groups()[0]
        mo = re.search(r'charset\s*=\s*(.+)', content, re.I + re.S)
        if mo:
            return mo.groups()[0]

def make_patterns(*args):
    importlib.reload(langs["python"])
    kw_pattern = '|'.join([r'\b{}\b'.format(kw)
        for kw in langs["python"].keywords])
    builtins_pattern = '|'.join([r'\b{}\b'.format(b)
        for b in langs["python"].builtins])
    patterns['.py'] = [(kw_pattern, 'keyword'), (builtins_pattern, 'builtin')]
    patterns['.py']+=[(square_brackets, 'square_bracket'),
        (parenthesis, 'parenthesis'), (curly_braces, 'curly_brace')]
    if docs:
        docs[current_doc].editor.syntax_highlight()

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
    if docs:
        Searcher().replace()

def run(*args):
    if not docs or not docs[current_doc].editor.zone.get(1.0, END).strip():
        return
    if docs[current_doc].file_name is None:
        save_as()
    file_ext = os.path.splitext(docs[current_doc].file_name)[1]
    editor = docs[current_doc].editor
    lang, begin, end = editor.get_infos(INSERT)
    if lang != "python":
        tkinter.messagebox.showerror(title='Execution error',
            message=_('not_python'))
        return
    save() # in case text or encoding changed
    # check if first line indicates interpreter
    linestart = editor.zone.index(begin + "linestart")
    lineend = editor.zone.index(begin + "lineend")
    first_line = docs[current_doc].editor.zone.get(linestart, lineend)
    if first_line.startswith('#!'):
        interp = first_line[2:]
    else:
        interp = dict(python_versions)[python_version.get()]
    if interp.lower().endswith('w.exe'):
        # On Windows, use python.exe, not pythonw.exe
        interp = interp[:-5] + interp[-4:]
    if ' ' in interp:
        interp = '"{}"'.format(interp)
    this_dir = os.path.dirname(__file__)
    script_dir = os.path.dirname(docs[current_doc].file_name)
    save_sys_path = sys.path[:]
    if file_ext == ".py":
        fname = docs[current_doc].file_name
    else:
        temp_name = 'temp_TedPy.py'
        fname = os.path.join(script_dir, temp_name)
        with open(fname, "w", encoding="utf-8") as out:
            out.write(editor.zone.get(begin, end))
    if sys.platform == 'win32':
        # use START in file directory
        with open(os.path.join(this_dir, "run.bat"), "w",
                encoding="utf-8") as out:
            out.write(f"@echo off\n%1%\ncd %2%\n{interp} %3%\npause")
            if file_ext != '.py':
                out.write('\ndel %3%')
            out.write('\nexit')
        save_dir = os.getcwd()
        drive = os.path.splitdrive(script_dir)[0]
        os.chdir(drive)
        dname = script_dir.replace('/', '\\')
        os.chdir(script_dir)
        cmd = r'start {} {} "{}" "{}"'.format(os.path.join(this_dir, "run.bat"),
            drive, dname, fname)
        try:
            os.system(cmd)
            os.chdir(save_dir)
            sys.path = save_sys_path
        except Exception as exc:
            print('exception', exc)
            import traceback
            traceback.print_exc(file=sys.stderr)

    else:   # works on Raspbian
        with open('run.sh', 'w', encoding='utf-8') as out:
            out.write('#!/bin/bash\ncd {}\n{} {}\n'.format(
                os.path.dirname(fname), interp, os.path.basename(fname)))
        subprocess.Popen('/usr/bin/x-terminal-emulator -e "/bin/bash run.sh"',
            shell=True)

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
    enc = 'utf-8'
    try:
        data = zone.get(1.0, '{}-1c'.format(END)).encode(enc)
    except UnicodeEncodeError as msg:
        message = _('cannot_encode').format(enc)
        start = msg.start
        text = zone.get(1.0,'{}-1c'.format(END))
        line = 1 + text[:start].count('\n')
        if line==1:
            col = start
        else:
            col = len(text[text.rfind('\n', 0, start):start])
        message += '\nInvalid character line {}, column {}'.format(line, col)
        message += '\nafter '+text[start - 10:start]
        tkinter.messagebox.showerror('Encoding error',
            message=message)
        return False
    # set linefeed
    data = set_linefeed(data)
    with open(doc.file_name, 'wb') as out:
        out.write(data)
    doc.text = zone.get(1.0, '{}-1c'.format(END))
    return True

def search(*args):
    if docs:
        Searcher().search()

def search_in_files(*args):
    if docs:
        Searcher().search_in_files()

def set_fonts():
    global font, sh_font, italic_font

    root_w = root.winfo_screenwidth()
    fsize = config.get("font-size", -int(root_w / 90))

    families = tkinter.font.families(root)
    if "Consolas" in families:
        family = "Consolas"
    else:
        family = "Courier New"
    font = tkinter.font.Font(family=family, size=fsize)
    italic_font = tkinter.font.Font(family=family, size=fsize,
        slant="italic")
    sh_font = tkinter.font.Font(family=family, size=int(1.5 * fsize),
        weight="bold")
    bold_italic_font = tkinter.font.Font(family=family, size=int(1.5 * fsize),
        weight="bold", slant="italic")

def set_sizes():
    # file browser covers 15% of width
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    ratio = w / font.measure('0')
    for doc in docs:
        doc.editor.zone['width'] = int(0.85 * ratio)

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


def switch_to(new_index):
    global current_doc
    docs[current_doc].editor.frame.pack_forget()
    new_doc = docs[new_index]
    current_doc = new_index
    docs[current_doc].editor.frame.pack()
    root.title('TedPy - {}'.format(docs[current_doc].file_name))
    file_browser.select(new_doc)
    docs[current_doc].editor.zone.focus()
    syntax_highlight.set(getattr(docs[current_doc].editor, "highlight", True))

def update_highlight(*args):
    # update syntax highlighting if option is reset by user
    if docs:
        docs[current_doc].editor.syntax_highlight()

target = IntVar(root)
full_word = BooleanVar(root)
full_word.set(True)
case_insensitive = BooleanVar(root)
case_insensitive.set(True)
regular_expression = BooleanVar(root)
regular_expression.set(False)
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
menuModule.add_command(label=_('run'), accelerator="Ctrl+R", command=run)
nb_menu_items = menuModule.index(END)

menubar.add_cascade(menu=menuModule, label=_('file'))

menuEdition=Menu(menubar, tearoff=0)
menuEdition.add_command(label=_('search'), command=search, accelerator="F5")
menuEdition.add_command(label=_('search in files'), command=search_in_files,
    accelerator="F6")
menuEdition.add_command(label=_('replace'), command=replace, accelerator="F8")
menubar.add_cascade(menu=menuEdition, label=_('edit'))

root.config(menu=menubar)

root.bind('<Control-n>', new_module)
root.bind('<Control-o>', ask_module)
root.bind('<Control-s>', save)
root.bind('<Control-r>', run)
root.bind('<F5>', search)
root.bind('<F6>', search_in_files)
root.bind('<F8>', replace)
root.protocol('WM_DELETE_WINDOW', close_window)


# make root cover the entire screen, if supported by the OS
try:
    root.wm_state(newstate='zoomed')
except:
    root.wm_state(newstate='normal')

set_fonts()

root.geometry('{}x{}'.format(root.winfo_screenwidth(),
    root.winfo_screenheight()))
set_sizes()

right = Frame(root)

panel = Frame(right)
panel.pack(expand=YES, fill=BOTH)
right.pack(expand=YES, fill=BOTH)

check_file_change()

if len(sys.argv) > 1:
    open_module(sys.argv[1])

root.mainloop()
