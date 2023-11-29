extensions = ['.js', '.ts']
script_types = ['text/javascript']
struct_patterns = [r'^\s*\bfunction\*?\b',
                   r'^\s*.*=\s*function\*?\(.*',
                   r'^\s*.*:\s*function\*?\(.*'
                   ]
keywords = ['break','case','catch', 'const', 'continue','debugger',
    'default','delete','do','else','finally','for','function',
    'if','in','instanceof','let', 'new', 'of', 'return','switch','this',
    'throw','try','typeof','var','void','while','with', 'yield',
    'class','enum','export','extends','import','super',
    'true','false','null',
    'arguments', 'constructor','document',
    'length','location','prototype', 'window']
builtins = ['alert', 'eval', 'confirm', 'prompt', 'Array', 'RegExp']
zones = [('"', '"', 'string'), ("'", "'", 'string'), ("`", "`", 'string'),
        ('//', '\n', 'comment'), ('/*', '*/', 'comment')]
autoindent_lineend = '{'