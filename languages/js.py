extensions = ['.js']
script_types = ['text/javascript']
struct_patterns = [r'\bfunction\b', r'.*=\s*function\(.*\)', r'.*:\s*function\(.*\)']
keywords = ['break','case','catch', 'const', 'continue','debugger',
    'default','delete','do','else','finally','for','function',
    'if','in','instanceof','let', 'new','return','switch','this',
    'throw','try','typeof','var','void','while','with',
    'class','enum','export','extends','import','super',
    'true','false','null',
    'arguments', 'constructor','document',
    'length','location','prototype', 'window']
builtins = ['alert', 'eval', 'confirm', 'prompt', 'Array', 'RegExp']
zones = [('"', '"', 'string'), ("'", "'", 'string'), ("`", "`", 'string'),
        ('//', '\n', 'comment'), ('/*', '*/', 'comment')]
autoindent_lineend = '{'