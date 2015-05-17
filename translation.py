#!python
import os
import configparser
path = 'translations.ini'
encoding = 'utf-8'
ini = configparser.ConfigParser()
ini.read([path],encoding=encoding)

language = 'fr'

def translate(src):
    if not ini.has_section(src):
        return src
    try:
        return ini.get(src,language)
    except configparser.NoOptionError:
        try:
            return ini.get(src,'default')
        except configparser.NoOptionError:
            return src 