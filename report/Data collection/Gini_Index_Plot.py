#!/usr/bin/env python3

import requests
import re
import numpy as np
import random
import matplotlib as mpl
mpl.use('pgf')

import matplotlib.pyplot as plt
import matplotlib.lines as mlines


def gini_index(array):
    """
    Calculate the Gini coefficient of a numpy array.
    """
    array = array.flatten()
    if np.amin(array) < 0:
        array -= np.amin(array)  # values cannot be negative
    array += 0.0000001  # values cannot be 0
    array = np.sort(array)  # values must be sorted
    index = np.arange(1, array.shape[0]+1)  # index per array element
    n = array.shape[0]  # number of array elements
    return ((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))

# List of projects of which we want to draw the plot
# The first element of the tuple is used to indicate wheter a project has
# a log Gini index (False) or a high Gini index (True)
projects = [
    ('^', 'https://api.github.com/repos/apache/jackrabbit-oak', '#52E8BA', 'Jackrabbit Oak'),
    ('^', 'https://api.github.com/repos/apache/hadoop', '#5A61FF', 'Hadoop'),
    ('^', 'https://api.github.com/repos/apache/ofbiz', '#E0FF67', 'Ofbiz'),
    ('o', 'https://api.github.com/repos/apache/wicket', '#FF5A98', 'Wicket'),
    ('o', 'https://api.github.com/repos/apache/isis', '#616161', 'Isis'),
    ('o', 'https://api.github.com/repos/apache/camel', '#E8A952', 'Camel'),
]

for project_tuple in projects:
    marker, url, color, name = project_tuple

    base_url = url + '/contributors'

    r = requests.get(
        base_url, auth=('joined', '7fb42c90a8b83b773082e1a337fec4555f65c893'))

    # Store in a list the number of contributions of each contributor
    contributors = [contributor['contributions'] for contributor in r.json()]

    # If there are more contributors to retrieve, do it
    if 'Link' in r.headers:
        matches = re.findall(r'<.+?page=(\d+)>', r.headers['Link'])

        next_page, last_page = (int(p) for p in matches)

        for page in range(next_page, last_page + 1):
            url = base_url + '?page={}'.format(page)
            r = requests.get(
                url, auth=('joined', '7fb42c90a8b83b773082e1a337fec4555f65c893'))

            contributors.extend([contributor['contributions'] for contributor in r.json()])

    # Normalize each number of contributions by the total number of contributions
    contributors = [contributions / sum(contributors) for contributions in contributors]

    plt.plot(contributors, color=color, marker=marker, markersize=4, linewidth=2.0)

plt.ylabel('Number of contributions, normalized')
plt.xlabel('Contributors, ordered by n. of contributions')
plt.legend(handles=[mlines.Line2D([], [], marker=marker, color=color, linewidth=2.0, label=name)
                    for marker, _, color, name in projects])
plt.xlim(0, 55)
plt.ylim(0, 0.22)
plt.savefig('figure.pgf')
