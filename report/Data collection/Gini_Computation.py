#!/usr/bin/env python3

import requests
import sys
import csv
import re
import numpy as np


def gini_index(array):
    """
    Calculate the Gini coefficient of a numpy array
    """
    array = array.flatten()
    if np.amin(array) < 0:
        array -= np.amin(array)  # values cannot be negative
    array += 0.0000001  # values cannot be 0
    array = np.sort(array)  # values must be sorted
    index = np.arange(1, array.shape[0]+1)  # index per array element
    n = array.shape[0]  # number of array elements
    return ((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))

input_file = sys.argv[1]

# Store all the projects read from the CSV file in a list
projects = []
with open(input_file, newline='') as csvfile:
    reader = csv.reader(csvfile, delimiter=',', quotechar='"')

    # Skip the first line with the header
    next(reader)

    for row in reader:
        # Save the url of the repo and the name in the list
        projects.append((row[1], row[3]))

result = []

# Iterate over all the projects and calculate the Gini coefficient
# for each of them, storing the results in the result list
for project_tuple in projects:
    project_url, project_name = project_tuple

    base_url = project_url + '/contributors'

    # Make request to the Github API
    r = requests.get(
        base_url,
        auth=('joined','7fb42c90a8b83b773082e1a337fec4555f65c893'))

    contributors = []

    # If the project doesn't exist skip to the next one
    if r.status_code != 200:
        result.append({'project_name': project_name})
        continue

    cur_contributors = r.json()

    # If the response was empty for some reason skip to the next project
    if not cur_contributors:
        result.append({'project_name': project_name})
        continue

    # Store the number of contributions of each contributor in a list
    contributors = []

    for contributor in r.json():
        contributors.append(contributor['contributions'])

    # If there are more contributors to be downloaded, do it
    if 'Link' in r.headers:
        # Find first and last page of the results
        matches = re.findall(r'<.+?page=(\d+)>', r.headers['Link'])

        next_page, last_page = (int(p) for p in matches)

        # For each results page add the contributions to the list
        for page in range(next_page, last_page + 1):
            url = base_url + '?page={}'.format(page)
            r = requests.get(
                url,
                auth=('joined', '7fb42c90a8b83b773082e1a337fec4555f65c893'))

            for contributor in r.json():
                contributors.append(contributor['contributions'])

    # Compute the Gini index from the array with contributions
    gini_coeff = gini_index(np.array(contributors, dtype='float64'))

    # Store the result in the result list
    result.append({
        'project_name': project_name,
        'gini_index': gini_coeff,
        'n_contributions': sum(contributors),
        'n_contributors': len(contributors)
    })

output_file = sys.argv[2]

# Save the results to the CSV output file
with open(output_file, 'w', newline='') as csvfile:
    fieldnames = [
        'project_name',
        'gini_index',
        'n_contributions',
        'n_contributors'
    ]

    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for project in result:
        writer.writerow(project)
