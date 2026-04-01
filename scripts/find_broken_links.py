import os
import re
import requests
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


def check_link_broken(url, file_path):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 404:
            return True
    except requests.RequestException as e:
        print(f"Error accessing {url} in file {file_path}: {e}\n")
    return False


def main():
    #change directory if necessary
    files = find_files(".")
    broken_links = collections.defaultdict(list)
    for file_path in files:
        links = extract_links(file_path)
        for link in links:
            if check_link_broken(link, file_path):
                broken_links[link].append(file_path[1:])
    with open("broken_links.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Link", "File Path"])
        for link, file_paths in broken_links.items():
            for file_path in file_paths:
                writer.writerow([link, file_path])


if __name__ == "__main__":

    path = "."
    main()
