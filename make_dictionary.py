"""Build a dictionary of all functions and #define"""

import os
import re
import json

this_dir = os.getcwd()

# Load config
config_file = os.path.join(this_dir, 'config.json')
with open(config_file, encoding='utf-8') as f:
    config = json.load(f)

cpython_dir = config['cpython']

def_table = []
func_table = []

define_pattern = r'^#define\s+\b(?P<name>.+?)\b'
func_pattern = r'^(?P<name>[a-zA-Z0-9_]+)\('

nb = 0

table_dir = os.path.join(this_dir, 'tables')
if not os.path.exists(table_dir):
    os.mkdir(table_dir)

files = []

for dirpath, dirnames, filenames in os.walk(cpython_dir):
    if nb > 10000:
        break
    for filename in filenames:
        ext = os.path.splitext(filename)[1]
        if ext in ['.c', '.h']:
            path = os.path.join(dirpath, filename)
            short_path = path[len(cpython_dir) + 1:]
            nb += 1

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                found = False
                for mo in re.finditer(define_pattern, content, flags=re.M):
                    if found is False:
                        files.append(short_path + '\n')
                        file_num = len(files) - 1
                        found = True
                    line_num = content[:mo.start()].count('\n') + 1
                    name = mo.group('name')
                    def_table.append(f'{name} {line_num} {file_num}\n')

                for mo in re.finditer(func_pattern, content, flags=re.M):
                    if found is False:
                        files.append(short_path + '\n')
                        file_num = len(files) - 1
                        found = True
                    line_num = content[:mo.start()].count('\n') + 1
                    name = mo.group('name')
                    func_table.append(f'{name} {line_num} {file_num}\n')

print(nb)
print(len(def_table), 'defines')
print(len(func_table), 'functions')

with open(os.path.join(table_dir, 'files'), 'w', encoding='utf-8') as out:
    out.writelines(files)

def_table.sort()
with open(os.path.join(table_dir, 'defines'), 'w', encoding='utf-8') as out:
    out.writelines(def_table)

func_table.sort()
with open(os.path.join(table_dir, 'functions'), 'w', encoding='utf-8') as out:
    out.writelines(func_table)

