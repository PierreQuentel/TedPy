import keyword
import builtins
keywords = keyword.kwlist
builtins = dir(builtins)
zones = [ ('"""', '"""', 'string'), ("'''", "'''", 'string'),
        ('"', '"', 'string'), ("'", "'", 'string'),
        ('#', '\n', 'comment')]
extensions = ['.py']
script_types = ['text/python', 'text/python3']
struct_patterns = [r'\bdef\b', r'\bclass\b']
autoindent_lineend = ':'