#! /usr/bin/env python3
import re
import sys

sys.dont_write_bytecode = True
INTERESTS_LIST_FILE = "interests.list"

new_term = input('Enter the new term: ')

if len(new_term) < 1:
    raise Exception("Too short term to be added")

current_list = [new_term]
print(f'Reading data from {INTERESTS_LIST_FILE}')
with open(INTERESTS_LIST_FILE) as src:
    for line in src.readlines():
        if re.search(new_term, line):
            print(f'The term "{new_term}" is already in file "{INTERESTS_LIST_FILE}"')
            sys.exit(1)
        current_list.append(line.rstrip())


output = "\n".join(sorted(current_list))
print(f'Writting data {INTERESTS_LIST_FILE}')
with open(INTERESTS_LIST_FILE, "w") as dst:
    dst.write(output)

print(f"Term \"{new_term}\" added")

