# TedPy
Text editor for Python programs

Supports

- syntax highlighting for HTML markup and for programs in Javascript and
  Python, including programs inside HTML <script> tags
- program structure by right-click on a blank zone
- right-click on an identifier shows its occurrences in the program
- support several encodings
- Python auto-indent
- unlimited undo / redo
- execution of Python scripts, choosing between several Python versions if
  required

Configuration

- 2 color themes are provided in files __`config_white.json`__ and
  __`config_dark.json`__; set the content of __`config.json`__ to one of
  these to choose the theme
- the option `versions` of __`config.json`__ can be set to a list of
  `[version_name, interpreter_path]` list with all the Python versions present
  on the computer, eg:

```
version = ["Python 3.8", "e:/Python38/python.exe"]
```
- the option "encodings" can be set to specify additional encodings besides
  those provided by default : ascii, iso-8859-1, utf-8
  