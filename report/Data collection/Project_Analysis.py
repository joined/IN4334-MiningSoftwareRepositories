#!/usr/bin/env python3

import sh  # to interact with the shell
import re  # for regular expressions
import requests  # to download JIRA Bug list
import csv  # to save the results
import time # to sleep
import sys # command line arguments
import logging # logging status to log file
from collections import defaultdict, Counter
from datetime import datetime, timezone

if len(sys.argv) < 2:
    print("Usage: ./script.py logfile")
    sys.exit(1)

# We use a logfile to store the execution progress
logging.basicConfig(filename=sys.argv[1], level=logging.INFO)
info = logging.info

###############################################################################
# START PER-PROJECT CONFIGURATION #############################################
###############################################################################
# Name of the git repository
repo_name = 'hadoop'

# Tags of the releases we are analyzing, ordered by date
release_tags = [
    'release-2.4.1',
    'release-2.5.0',
    'release-2.5.1',
    'release-2.6.0',
    'release-2.7.0',
    'release-2.7.1',
    'release-2.6.1',
    'release-2.6.2',
    'release-2.6.3'
]

# The keys used to identify the project in Jira
# For certain projects, like Hadoop, multiple keys are used
jira_keys = [
    'HADOOP',
    'HDFS',
    'MAPREDUCE',
    'YARN'
]
###############################################################################
# END PER-PROJECT CONFIGURATION ###############################################
###############################################################################

###############################################################################
# START GLOBAL CONFIGURATION ##################################################
###############################################################################
jira_pause_seconds = 2
time_format_git = "%Y-%m-%d %H:%M:%S %z"
time_format_jira = "%Y-%m-%dT%H:%M:%S.%f%z"
compute_bug_info = True
###############################################################################
# END GLOBAL CONFIGURATION ####################################################
###############################################################################

git = sh.git.bake(_cwd=repo_name)

###############################################################################
# 1ST STEP: ###################################################################
# Create data structure containing for each release the list of files present #
# at the time of the release and compute the release start and end time #######
###############################################################################


def get_tag_date_time(tag):
    """
    Used to get the timestamp corresponding
    to a tag
    """
    raw_datetime = str(git('--no-pager', 'log', '-1', '--format=%ai',
                           'tags/{}'.format(tag)))[:-1]

    return datetime.strptime(raw_datetime, time_format_git)


# Main data structure of the script
d = {}

print("Populating initial data structure")

# Populate initial data structure with the start, end date and next release date
# of each release and the list of files present at the time of release.
for index, release_tag in enumerate(release_tags):
    # Skip first release because we don't know when it started
    if index == 0:
        continue

    start_date = get_tag_date_time(release_tags[index-1])
    end_date = get_tag_date_time(release_tag)

    # For the latest release we set the time of next release to the current
    # date time
    if index == len(release_tags) - 1:
        next_release_date = datetime.now(tz=timezone.utc)
    else:
        next_release_date = get_tag_date_time(release_tags[index+1])

    print("Adding release {} with start date {}, end date {} and "
          "next release date {}".format(
              release_tag, start_date, end_date, next_release_date))

    files_in_current_release = str(git('ls-tree', '--name-only', '-r',
                                       release_tag)).split('\n')[:-1]
    java_files_in_current_release = [file for file in files_in_current_release
                                     if file.endswith('.java')]
    d[release_tag] = {
        'start_date': start_date,
        'end_date': end_date,
        'next_release_date': next_release_date,
        'file_info': {file: {
            'buggy': False,
            'bug_discovered_after_next_release': False,
            'metrics': {'comm': 0, 'adev': 0, 'ddev': 0, 'add': 0, 'del': 0,
                        'own': 0, 'minor': 0}
        } for file in java_files_in_current_release}
    }

###############################################################################
# 2ND STEP: ###################################################################
# Retrieve the bug information from JIRA and mark buggy files as such #########
###############################################################################

# Base URL for the API used to retrieve commits fixing bugs
base_commit_url = "https://issues.apache.org/jira/rest/dev-status/1.0/issue/"\
                  "detail?applicationType=fecru&dataType=repository"

# In this dictionary we store all the commits that fixed a bug.
# The keys of the dictionary are the bugfix commits hashes and the values
# are dictionaries containing the timestamp of the bugfix commit and the
# list of files with lines removed by the commit.
# This way we know for each commit which files to blame to understand in
# which release the bug was introduced
bug_fixing_commits = {}


def add_bug(issue_id):
    """
    Given a bug issue ID, this function retrieves
    the commit info attached to the issue in order
    to identify the commits that fixed the issue
    """
    req_url = base_commit_url + "&issueId={}".format(issue_id)

    # Repeat to overcome JIRA rate limiting
    while True:
        try:
            results = requests.get(req_url).json()
            break
        except:
            time.sleep(jira_pause_seconds)

    # Get the list of repositories with commits attached to the issue
    repositories = results['detail'][0]['repositories']

    # If there is at least one commit attached to the issue
    if repositories:
        for fixing_commit in repositories[0]['commits']:
            commit_hash = fixing_commit['id']

            # Only add the current commit as bug fixing commit
            # if it's not already listed
            if commit_hash not in bug_fixing_commits:
                # Get the list of files changed by the commit that had
                # at least one line removed, and are Java files
                files_with_lines_removed = [file['path']
                                            for file in fixing_commit['files']
                                            if file['linesRemoved'] != 0 and
                                            file['path'].endswith('.java')]

                # Add the commit together with the files that had some lines
                # removed to the dictionary, only if the commit removed some
                # lines
                if files_with_lines_removed:
                    commit_timestamp = datetime.strptime(
                        fixing_commit['authorTimestamp'],
                        time_format_jira)

                    bug_fixing_commits[commit_hash] = {
                        'files_with_lines_removed': files_with_lines_removed,
                        'commit_timestamp': commit_timestamp
                    }

print("Retrieving defect information from JIRA")

# We have to get from the Jira REST API the lists of issue IDs that
# correspond to a bug. the API allows the retrieval of only ~50
# results at time, meaning we have to repeat the request multiple
# times in order to get all the issue IDs
jira_api_url = 'https://issues.apache.org/jira/rest/api/2/search'

# We only ask for bugs that are marked as fixed, and have a creation
# date next to the start date of the first release
jql = "({}) AND issuetype = Bug AND resolution = Fixed AND "\
      "created >= {}".format(
          ' OR '.join(['project = {}'.format(key) for key in jira_keys]),
          get_tag_date_time(release_tags[0]).strftime("%Y-%m-%d"))

print("JIRA query: {}".format(jql))

first_results = requests.post(jira_api_url,
                              json={'jql': jql,
                                    'fields': ['key']}).json()
maxResults = first_results['maxResults']
total = first_results['total'] if compute_bug_info else 0

print("Total number of issues to analyze: {}".format(total))

for startAt in range(0, total, maxResults):
    payload = {
        'jql': jql,
        'fields': ['key'],
        'startAt': startAt
    }

    # The JIRA API has rate limiting, so if the request is not
    # sucessful we try again
    while True:
        try:
            results = requests.post(jira_api_url, json=payload).json()
            break
        except:
            time.sleep(jira_pause_seconds)

    for issue in results['issues']:
        info("Retrieving commit info for bug {}".format(issue['key']))
        add_bug(issue['id'])

    print("Analyzed {} out of {} issues".format(startAt + maxResults, total))

bugfixing_commits_len = len(bug_fixing_commits)

# At this point we have, in bug_fixing_commits, the commits that
# fixed some defects together with the list of files that had
# some lines removed by those commits.
# The next step is then to blame each of those files to understand
# in which release they were introduced.

# Pattern used to identify removed linenumbers
# We compile it just one time to improve speed
removed_linenumbers_pattern = re.compile(
    r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@',
    flags=re.M)

# Pattern used to identify line number, timestamp and filename in git blame
# output
line_tstamp_file_pattern = re.compile(
    '^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?(?:\n.*?)+'
    'author-time (\d+)(?:\n.*?)+'
    'filename (.+?)$',
    flags=re.M)


def get_bug_introduction_info(bugfix_commit_hash, bugfixed_file):
    """
    Given a bugfix commit hash and a file with lines
    removed by that commit, returns the list of commits
    that introduced the lines removed by the bugfix commit,
    together with their timestamp and the original file name
    """

    # First we need to know which are the lines that were removed
    # to fix the bug. For this purpose we use git show as follows.
    # Apparently some commits can be removed from the history of the
    # repository, in that case we ignore them
    try:
        cmd = ('--no-pager', 'show', '--no-color', '--format=',
               '--unified=0', commit_hash, '--', bugfixed_file)

        raw_show_output = str(git(*cmd))
    except:
        return None

    # The output of git show contains the removed line groups,
    # each one in the following format:
    # @@ -X,Y +Z,W @@
    # ..content of removed lines..
    # where X is the start line of the removed group
    # and Y is the number of lines removed.
    # If Y = 0 no lines were removed, while
    # if Y is not present it means 1 line was removed.

    # Find all patterns corresponding to removed line numbers
    removed_lines_matches = \
        removed_linenumbers_pattern.finditer(raw_show_output)

    # In removed_lines_ranges we store all the ranges of lines removed
    # by the current commit
    removed_lines_ranges = []
    for match in removed_lines_matches:
        _start_line, _n_lines = match.groups()
        start_line = int(_start_line)
        n_lines = int(_n_lines) if _n_lines is not None else 1

        if n_lines != 0:
            end_line_included = start_line + n_lines - 1

            removed_lines_ranges.append((start_line, end_line_included))

    # Now that we know the ranges of removed lines, we blame the file
    # to understand from where each line comes from
    blame_out = str(git('--no-pager', 'blame', '--line-porcelain',
                        bugfix_commit_hash + '^1', '--', bugfixed_file))

    line_tstamp_file_matches = \
        line_tstamp_file_pattern.finditer(blame_out)

    # We use a set to store all the (commit, timestamp, original_filename)
    # tuples that introduced a bug
    commit_tstamp_filename_tuples = set()

    for match in line_tstamp_file_matches:
        commit, line_n, _timestamp, filename = match.groups()
        timestamp = datetime.fromtimestamp(int(_timestamp), timezone.utc)

        # Check if the current line was removed in the bugfix commit
        if any(start_line <= int(line_n) <= end_line
               for start_line, end_line in removed_lines_ranges):
            commit_tstamp_filename_tuples.add((commit, timestamp, filename))

    return commit_tstamp_filename_tuples

print("Linking bugfix commits to releases")

# Iterate over all the bug fixing commits
for index, (commit_hash, commit_info) in enumerate(bug_fixing_commits.items()):
    info('Processing bugfixing commit {} out of {}'.format(
        index, bugfixing_commits_len))

    date_time_fixing = commit_info['commit_timestamp']
    defective_files = commit_info['files_with_lines_removed']

    for defective_file in defective_files:
        # Get the information about when and where the bug was introduced
        # In particular the get_bug_introduction_info function will return
        # a set of (commit, timestamp, filename) tuples where a bug was
        # introduced with commit "commit" at "timestamp" in file "filename"
        bug_introduction_info = get_bug_introduction_info(
            commit_hash, defective_file)

        if bug_introduction_info is None:
            continue

        # Iterate over all the bug introductions
        for commit, date_time_introduction, filename in bug_introduction_info:
            info("A bug was introduced in file {} at timestamp {} and was "
                 "fixed at time {}".format(
                     filename,
                     date_time_introduction,
                     date_time_fixing))

            # Iterate over all the releases
            for release, release_info in d.items():
                # Get the datetime of start, end and of the next release
                start_date = release_info['start_date']
                end_date = release_info['end_date']
                next_release_date = release_info['next_release_date']

                # If the bug that we're analyzing was introduced in the
                # time of development of the current release
                if (start_date < date_time_introduction < end_date):
                    # If the file was present at the time of release
                    # mark it as buggy
                    if filename in release_info['file_info']:
                        release_info['file_info'][filename]['buggy'] = True

                        # If the bug was fixed after the next release,
                        # it means we cannot use it in the training set
                        # so we signal this with a flag
                        if date_time_fixing > next_release_date:
                            release_info['file_info'][filename]['bug_discovered_after_next_release'] = True

###############################################################################
# 3RD STEP: ###################################################################
# Compute the metrics for each file in each release ###########################
###############################################################################

author_email_pattern = re.compile(r'author-mail <(.+?)>\nauthor-time (\d+)',
                                  flags=re.M)

for release, release_info in d.items():
    print("Computing metrics for release {}".format(release))

    start_date = release_info['start_date']
    end_date = release_info['end_date']

    # To compute COMM and ADEV we look at all the commits made in this release

    # Get the list of all commits made in this release together with the commit
    # author email and the files changed by each commit
    #
    # [author_email_1]
    # path/to/A.java
    # path/to/B.java
    #
    # [author_email_2]
    # path/to/C.java
    # path/to/D.java
    cmd = ('--no-pager', 'log', '--name-only',
           '--after="{}"'.format(start_date),
           '--before="{}"'.format(end_date),
           '--pretty=format:[%ae]')

    raw_log_output = str(git(*cmd))

    # We create a dictionary in which each file modified in one of the commits
    # that we're analyzing is a key and the corresponding value is a list
    # of the authors that made a change to this file
    temp_d = defaultdict(list)

    for raw_group in raw_log_output.split('\n\n'):
        if not raw_group.strip():
            continue

        commit_group = raw_group.split('\n')

        # If it's an empty commit, skip it
        if len(commit_group) < 2:
            continue

        author_email = commit_group[0][1:-1]
        changed_files = commit_group[1:]

        # Filter our non-Java files
        filter(lambda f: f.endswith('.java'), changed_files)

        for file in changed_files:
            temp_d[file] += author_email

    for file, authors in temp_d.items():
        if file in release_info['file_info']:
            # COMM = number of commits made to this file in this release
            # Since we add to the author list of the file the author
            # of each commit, the number of authors equals to the number
            # of commits
            release_info['file_info'][file]['metrics']['comm'] = len(authors)

            # ADEV = number of distinct developers who contributed to the
            # file in this release
            release_info['file_info'][file]['metrics']['adev'] = \
                len(set(authors))

    info("COMM and ADEV computed for release {}".format(release))

    files_in_release_len = len(release_info['file_info'])

    # To compute DDEV we use the "git shortlog" command on every file of
    # each release
    for index, (file, file_info)\
            in enumerate(release_info['file_info'].items()):
        info('Computing DDEV for file {} out of {}'.format(
            index, files_in_release_len))
        cmd = ('--no-pager', 'shortlog', '-s', '--email',
               'origin..{}'.format(release), '--', file)
        raw_shortlog_output = str(git(*cmd))

        if not raw_shortlog_output.strip():
            continue

        # DDEV = number of distinct developers who contributed to the file
        # since the beginning of time.
        # The output of shortlog contains one line for each distinct developer
        # that has contributed to the file.
        file_info['metrics']['ddev'] = len(raw_shortlog_output.split('\n')) - 1

    # Computation of ADD and DEL
    # We use the numstat option to get, for each commit in the current release,
    # the list of files modified each with its corresponding number of added
    # and deleted lines
    info('Computing ADD and DEL')

    cmd = ('--no-pager', 'log', '--pretty=', '--numstat',
           '--after="{}"'.format(start_date),
           '--before="{}"'.format(end_date))

    raw_log_output = str(git(*cmd))

    total_added_lines, total_removed_lines = 0, 0

    for line in raw_log_output.split('\n'):
        if not line.strip():
            continue

        added_lines, removed_lines, filename = line.split('\t')

        # For some reason the number of added lines or removed lines
        # can be '-', maybe because an empty file was created?
        # In that case we skip to the next change
        if '-' in (added_lines, removed_lines):
            continue

        total_added_lines += int(added_lines)
        total_removed_lines += int(removed_lines)

        # If the modified file that we're analyzing was there at the time
        # of the release, increase its count of added/deleteed lines
        # by the number of added/deleted lines in the current change
        if filename in release_info['file_info']:
            release_info['file_info'][filename]['metrics']['add'] += \
                int(added_lines)
            release_info['file_info'][filename]['metrics']['del'] += \
                int(removed_lines)

    # Normalize the added and deleted lines of each file by the total number
    # of added and deleted lines in the project
    # ADD = normalized (by the total number of added lines) added lines
    # in the file
    # DEL = normalized (by the total number of deleted lines) deleted lines
    # in the file
    for file, file_info in release_info['file_info'].items():
        file_info['metrics']['add'] /= total_added_lines
        file_info['metrics']['del'] /= total_removed_lines

    # Computation of OWN and MINOR
    for index, (file, file_info)\
            in enumerate(release_info['file_info'].items()):
        info('Computing OWN and MINOR for file {} out of {}'.format(
            index, files_in_release_len))

        # We blame each file at state just before the final release
        # commit
        cmd = ('--no-pager', 'blame', '--line-porcelain',
               '{}^1'.format(release), '--', file)

        raw_blame_output = str(git(*cmd))

        if not raw_blame_output.strip():
            continue

        lines = author_email_pattern.finditer(raw_blame_output)

        line_contributors = []
        # We iterate over all the lines of the file and add the author
        # of the line to the list of contributors of the current file
        # only if the contribution was made after the date of start
        # of the current release
        for line in lines:
            author_email, timestamp = line.groups()

            if datetime.fromtimestamp(int(timestamp),
                                      timezone.utc) > start_date:
                line_contributors.append(author_email)

        # If there is no valid contributor (meaning all the lines in the file
        # were not modified in the current release) we leave OWN and MINOR to
        # 0 and we skip to the next file
        if not line_contributors:
            continue

        # Once we have the list of "valid" contributors for the current file,
        # we are able to compute the metrics
        line_contributors_counter = Counter(line_contributors)

        total_contributors = len(line_contributors_counter)
        total_lines = sum(line_contributors_counter.values())

        minor_contributors = sum(1 for contributor, value
                                 in line_contributors_counter.items()
                                 if value/total_lines <= 0.05)
        n_lines_best_contributor = max(line_contributors_counter.values())
        ownership_best_contributor = n_lines_best_contributor / total_lines

        # OWN = percentage of lines authored by the contributor that authored
        # the most lines
        # MINOR = number of contributors that authored less than 5% of
        # the lines
        file_info['metrics']['own'] = ownership_best_contributor
        file_info['metrics']['minor'] = minor_contributors

###############################################################################
# 4TH STEP: ###################################################################
# Save the results in a set of CSV files ######################################
###############################################################################

print("Saving results")

for release, release_info in d.items():
    end_date = release_info['end_date'].strftime("%Y-%m-%d")
    output_file = '{}-{}-{}.csv'.format(repo_name, end_date, release)

    with open(output_file, 'w', newline='') as csvf:
        fieldnames = ['file_name', 'comm', 'adev', 'ddev', 'add', 'del',
                      'own', 'minor', 'buggy', 'bug_discovered_after_next_release']

        writer = csv.DictWriter(csvf, fieldnames=fieldnames, delimiter=',')
        writer.writeheader()

        for file, file_info in release_info['file_info'].items():
            writer.writerow({
                'file_name': file,
                'comm': file_info['metrics']['comm'],
                'adev': file_info['metrics']['adev'],
                'ddev': file_info['metrics']['ddev'],
                'add': '%.6f' % file_info['metrics']['add'],
                'del': '%.6f' % file_info['metrics']['del'],
                'own': '%.6f' % file_info['metrics']['own'],
                'minor': file_info['metrics']['minor'],
                'buggy': file_info['buggy'],
                'bug_discovered_after_next_release':
                    file_info['bug_discovered_after_next_release']
            })