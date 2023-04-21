#! /usr/bin/env python3

INTERESTS_LIST_FILE = "interests.list"

new_term = input('Enter the new term: ')

if len(new_term) < 1:
    raise Exception("Too short term to be added")

current_list = []
with open(INTERESTS_LIST_FILE) as src:
    for line in src.readlines():
        current_list.append(line.rstrip())

with open(INTERESTS_LIST_FILE, "w") as dst:
    output = "\n".join(sorted(current_list))
    dst.write(output)

print(f"Term \"{new_term}\" added")

