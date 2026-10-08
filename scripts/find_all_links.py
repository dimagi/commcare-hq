import os
import re
import collections
import csv


def find_files(directory):
    file_list = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list


def extract_links(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()
    links = re.findall(r'https?://[^\s"\']*?(?:atlassian|confluence)[^\s"\']*', content)
    return links


def main():
    files = find_files(".")
    links_dict = collections.defaultdict(list)
    for file_path in files:
        links = extract_links(file_path)
        for link in links:
            links_dict[link].append(file_path[1:])
    with open("all_links.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Link", "File Path"])
        for link, file_paths in links_dict.items():
            for file_path in file_paths:
                writer.writerow([link, file_path])


if __name__ == "__main__":

    main()
