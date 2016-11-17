#!python
import os
import json

language = 'fr'
with open("translations_{}.json".format(language), encoding="utf-8") as fobj:
    translations = json.load(fobj)

def translate(src):
    return translations.get(src, src)