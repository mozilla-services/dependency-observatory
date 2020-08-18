a = open("npm-most-depended-raw.txt", "r")
content = a.read().split("\n")

i = 0
while i < len(content):
    print(content[i])
    i += 7
