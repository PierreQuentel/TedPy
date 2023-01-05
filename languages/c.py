extensions = ['.c', '.h']
script_types = ['text/javascript']
struct_patterns = [r'^[a-zA-Z0-9_]+\(.*\)', '#define .*']
keywords = [
    'auto',    'break',    'case',    'char',    'const',    'continue',    'default',    'do',
    'double',    'else', 'enum', 'extern',    'float',    'for',    'goto',    'if', 'int',
    'long',    'register',    'return',    'short', 'signed',    'sizeof','static',
    'struct',    'switch',    'typedef',    'union',    'unsigned',    'void',    'volatile',
    'while']
builtins = ['#include', '#define', '#ifndef', '#endif', 
            'NULL', 'RegExp']
zones = [('"', '"', 'string'), ("'", "'", 'string'), ("`", "`", 'string'),
        ('//', '\n', 'comment'), ('/*', '*/', 'comment')]
autoindent_lineend = '{'