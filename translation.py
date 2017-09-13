import os
import json

this_dir = os.path.dirname(__file__)

language = 'fr'
tr_path = os.path.join(this_dir, "translations_{}.json".format(language))
with open(tr_path, encoding="utf-8") as fobj:
    translations = json.load(fobj)

def translate(src):
    return translations.get(src, src)