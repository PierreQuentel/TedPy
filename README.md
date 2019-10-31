# TedPy

Text editor for HTML, Python and Javascript

## Supports

- syntax highlighting for HTML markup and for programs in Javascript and
  Python, including programs inside HTML <script> tags
- program structure by right-click on a blank zone
- right-click on an identifier shows its occurrences in the program
- a choice of encodings
- Python auto-indent
- unlimited undo / redo
- execution of Python scripts, choosing between several Python versions if
  required

## Configuration

The configuration file `config.json` has the following options:
- `theme` : one of the color themes in the subdirectory __`themes`__
  (currently only "Dark" or "White")
- `versions` : a list of `[version_name, interpreter_path]` lists with all the
  Python versions present on the computer, eg:

```
version = ["Python 3.8", "e:/Python38/python.exe"]
```
- `encodings` can be set to specify additional encodings besides
  those provided by default : ascii, iso-8859-1, utf-8
