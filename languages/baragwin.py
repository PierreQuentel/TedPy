import keyword
keywords = keyword.kwlist
builtins = dir(__builtins__)
builtins += ["Document", "Math", "Test", "Window"]
zones = [ ('"""', '"""', 'string'), ("'''", "'''", 'string'),
        ('"', '"', 'string'), ("'", "'", 'string'),
        ('#', '\n', 'comment')]
extensions = ['.bg']
script_types = ['text/baragwin']
struct_patterns = [r'\bdef\b', r'\bwhen\b']