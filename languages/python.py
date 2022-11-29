import keyword
import builtins
keywords = keyword.kwlist
builtins = dir(builtins)
zones = [ ('"""', '"""', 'string'), ("'''", "'''", 'string'),
        ('"', '"', 'string'), ("'", "'", 'string'),
        ('#', '\n', 'comment')]
extensions = ['.py']
script_types = ['text/python', 'text/python3']
struct_patterns = [r'\s*\bdef\b', r'\s*\bclass\b']
autoindent_lineend = ':'