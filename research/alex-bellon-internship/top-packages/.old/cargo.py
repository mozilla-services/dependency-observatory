a = open("cargo-most-depended.txt", "r").read().split("\n")
i = 0
while i in range(len(a)):
    print(a[i])
    i += 3
