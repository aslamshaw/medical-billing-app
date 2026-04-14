import os

ignore = {'.venv', '.idea', '__pycache__'}

for root, dirs, files in os.walk(".", topdown=True):
    dirs[:] = [d for d in dirs if d not in ignore]

    level = root.count(os.sep)
    indent = "│   " * level
    print(f"{indent}{os.path.basename(root)}/")

    for f in files:
        print(f"{indent}│   {f}")