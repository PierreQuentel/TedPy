import keyword
out = open("_patterns.py", "w")
out.write("keywords = "+str(keyword.kwlist)+"\n")
out.write("builtins = {}".format(dir(__builtins__)))
out.close()