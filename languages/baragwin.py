keywords = [
    "return", "break", "for", "lambda", "try", "finally",
    "raise", "def", "while", "del", "global",
    "as", "elif", "else", "if",
    "except", "raise", "in", "continue",
    "async", "await",
    "when", "on", "module", "yield"
    ]
builtins = [
    "abs", "all", "any", "callable", "chr",
    "delattr", "dir", "eval", "exec", "exit", "format", "getattr",
    "globals", "hasattr", "input", 
    "locals", "max", "min", 
    "open", "ord", "pow", "print", "repr", "round", "setattr",
    "sorted", "sum",
    "bool", "dict", "enumerate",
    "filter", "float", "int", "list", 
    "str", "type", "zip",
    'False',  'None', 'True',
    'Date', 'Info', 'Test'
]
builtins += ["Document", "Math", "Test", "Window"]
zones = [ ('"""', '"""', 'string'), ("'''", "'''", 'string'),
        ('"', '"', 'string'), ("'", "'", 'string'),
        ('#', '\n', 'comment')]
extensions = ['.bg']
script_types = ['text/baragwin']
struct_patterns = [r'\bdef\b', r'\bwhen\b']