import sh  # to interact with the shell
import re  # for regular expressions
import requests  # to download JIRA Bug list
import csv  # to save the results
import time
from collections import Counter, defaultdict  # useful structures

git = sh.git.bake(_cwd='lucene-solr')

# regex that matches path of Java files inside the core
core_regex = r'^lucene\/core\/src\/java\/org\/apache\/lucene.*?\.java$'

#########################################
# 1ST STEP ##############################
#########################################

start_date, end_date = "2013-01-01 00:00", "2013-12-31 23:59"

log_output = str(git('--no-pager', 'log', '--name-only', after=start_date,
                     before=end_date, pretty="format:[%H,%ai,%ae]"))
# output of git log will be:
#
# [commit_hash_1, author_timestamp_1, author_email_1]
# path/to/A.java
# path/to/B.java
#
# [commit_hash_2, author_timestamp_2, author_email_2]
# path/to/C.java
# path/to/D.java

splitted_output = (s.split('\n') for s in log_output.split('\n\n'))

# this structure is used to store all the results of the analysis
struct = {}

for commit_group in splitted_output:
    i = 0
    # empty commits appear on top of each commit group and we want to
    # filter them out
    while commit_group[i+1].startswith('['):
        i += 1

    commit_info = commit_group[i][1:-1]  # remove parenthesis at start and end
    commit_hash, author_date, author_email = commit_info.split(',')

    changed_files = commit_group[i+1:]
    # filter out files that are not Java or not in the core
    changed_files = filter(lambda f: re.search(core_regex, f), changed_files)

    for file_path in changed_files:
        struct[(commit_hash, file_path)] = {
            'author_date': author_date,
            'author_email': author_email,
            'bugs_info': {
                'counters': defaultdict(int),
                'lists': defaultdict(list)
            }
        }


def computeMetrics(counter, commit_author):
    """
    Used to compute commit/line metrics

    First argument is the contributors counter that looks like this:
    Counter({
        'contributor_mail_1': contributed_lines_1/contributed_commits_1,
        'contributor_mail_2': contributed_lines_2/contributed_commits_2,
        ...
    })
    """

    total_contributors = len(counter)
    total_value = sum(counter.values())

    minor_contributors = sum(1 for contributor, value in counter.items()
                             if value/total_value <= 0.05)
    major_contributors = sum(1 for contributor, value in counter.items()
                             if value/total_value > 0.05)

    commit_author_ratio = \
        counter[commit_author]/total_value if commit_author in counter else 0

    max_value_contributor = max(counter.keys(), key=(lambda k: counter[k]))

    ownership_best_contributor = counter[max_value_contributor] / total_value

    commit_author_is_best_contributor = \
        True if max_value_contributor == commit_author else False

    return {
        'total_contributors': total_contributors,
        'minor_contributors': minor_contributors,
        'major_contributors': major_contributors,
        'ownership_best_contributor': ownership_best_contributor,
        'commit_author_ratio': commit_author_ratio,
        'commit_author_is_best_contributor': commit_author_is_best_contributor
    }

# line contributors metrics computation
for ((commit_hash, file_path), info) in struct.items():
    try:
        blame_out = str(git('--no-pager', 'blame', file_path,
                            commit_hash + '^1', '--line-porcelain'))
    except sh.ErrorReturnCode_128:
        # the file was not found at that specific commit, meaning that it still
        # didn't exist. in this case we leave the line metrics empty
        continue

    # the output of git blame contains a contributors' email as many times as
    # the number of lines that he has written, so we just search
    # for all the emails in the output
    line_contributors = re.findall(r'author-mail <(.+?)>', blame_out,
                                   flags=re.M)
    line_contributors_counter = Counter(line_contributors)

    info['line_metrics'] = computeMetrics(line_contributors_counter,
                                          info['author_email'])

#########################################
# 2ND STEP ##############################
#########################################

# commit contributors metrics computation
start_date = "2011-01-01 00:00"

for ((commit_hash, file_path), info) in struct.items():
    end_date = info['author_date']
    contributors = str(git('--no-pager', 'log', '--after="%s"' % start_date,
                           '--before=%s' % end_date, '--follow',
                           '--pretty=%ae', '--', file_path))
    # output of log will be the list of authors of each commit one per line

    # if the file was created in the commit that we're analyzing, the output
    # will be empty. in that case we leave the commit metrics empty
    if not contributors:
        continue

    # last item is always an empty string
    commit_contributors = contributors.split('\n')[:-1]
    commit_contributors_counter = Counter(commit_contributors)

    info['commit_metrics'] = computeMetrics(commit_contributors_counter,
                                            info['author_email'])

#########################################
# 3RD STEP ##############################
#########################################

start_date, end_date = "2013-01-01 00:00", "2016-01-01 00:00"

raw_revlist_output = str(git('rev-list', 'master', '--timestamp',
                             pretty='oneline', after=start_date,
                             before=end_date))
# output of revlist will be:
# unix_timestamp_1 commit_hash_1 title_1
# unix_timestamp_2 commit_hash_2 title_2
# ...

commits_3rd_step = ({'title': commit[52:],
                     'hash': commit[11:40],
                     'tstamp': commit[:10]}
                    for commit in raw_revlist_output.split('\n')[:-1])

# we have to get from the Jira REST API the lists of issue IDs that
# correspond to a bug. the API allows the retrieval of only 100
# results at time, meaning we have to repeat the request multiple
# times in order to get all the issue IDs
jira_api_url = 'https://issues.apache.org/jira/rest/api/2/search'

payload = {
    'jql': 'project = LUCENE AND issuetype = Bug',
    'fields': ['key']
}
first_results = requests.post(jira_api_url, json=payload).json()
maxResults = first_results['maxResults']
total = first_results['total']

# we store in a list the issue IDs that correspond to a bug
bugs_issue_ids = []

for startAt in range(0, total, maxResults):
    payload = {
        'jql': 'project = LUCENE AND issuetype = Bug',
        'fields': ['key'],
        'startAt': startAt
    }
    results = requests.post(jira_api_url, json=payload).json()

    for issue in results['issues']:
        bugs_issue_ids.append(issue['key'])

    time.sleep(5)  # in order not to trigger the rate limiter

for commit in commits_3rd_step:
    post_release_bugs, dev_time_bugs = 0, 0

    # we look first for a Jira issue id in the commit message
    jira_match = re.search(r'LUCENE-\d{1,4}', commit['title'])

    if jira_match and jira_match.group() in bugs_issue_ids:
        post_release_bugs = 1
    else:
        # if we didn't find an issue id in the message, we look for a keyword
        keywords = ('error', 'bug', 'fix', 'issue', 'mistake', 'incorrect',
                    'fault', 'defect', 'flaw', 'typo')

        if any(keyword in commit['title'] for keyword in keywords):
            dev_time_bugs = 1

    bugs_induced_qty = dev_time_bugs + post_release_bugs

    if bugs_induced_qty > 0:
        # if the commit was a bugfix, we get the list of files that it changed
        changed_files = str(git('--no-pager', 'show', '--name-only',
                                '--pretty=', commit['hash'])).split('\n')[:-1]
        # output is list of changed files one per line

        # we are interested only in Java files in the core.
        # theoretically, a bug introduced in one of the Java core files
        # could have been "propagated" outside of the core directory, for
        # example if the buggy file was moved. we assume this is not the case
        # to reduce the complexity of the analysis.
        changed_files = filter(lambda f: re.search(core_regex, f),
                               changed_files)

        for file_path in changed_files:
            # after getting the list of files changed by the "bugfix" commit
            # we need to know for each file which lines were removed,
            # since we assume that those lines contained the bug
            raw_show_output = str(git('--no-pager', 'show', '--no-color',
                                      '--format=', '--unified=0',
                                      commit['hash'], '--', file_path))

            # the output of git show contains the removed line groups
            # each one in the following format:
            # @@ -X,Y +Z,W @@
            # ..content of removed lines..
            # where X is the start line of the removed group
            # and Y is the number of lines removed.
            # if Y = 0 no lines were removed.
            # if Y is not present it means 1 line was removed.

            # this regex matches the removed lines ranges
            removed_linenumbers_regex = \
                r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@'

            removed_lines_matches = re.finditer(removed_linenumbers_regex,
                                                raw_show_output, flags=re.M)

            # for convenience we add to a list the ranges of removed lines
            removed_lines_ranges = []
            for match in removed_lines_matches:
                _start_line, _n_lines = match.groups()
                start_line = int(_start_line)
                n_lines = int(_n_lines) if _n_lines is not None else 1

                if n_lines != 0:
                    end_line_included = start_line + n_lines - 1

                    removed_lines_ranges.append((start_line,
                                                 end_line_included))

            # if no line was removed from the file we are analyzing, we skip
            # to the next file
            if not removed_lines_ranges:
                continue

            # now that we know the ranges of removed lines, we blame the file
            # to understand from where each line comes from
            blame_out = str(git('--no-pager', 'blame', '--line-porcelain',
                                commit['hash'] + '^1', '--', file_path))

            # this regex matches the (commit, filepath) pair of each line
            # where 'commit' is the commit hash in which the line was
            # introduced and filepath is the original path of the file
            commit_and_filename_regex = \
                r'^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?(?:\n.*?)+?filename (.+?)$'

            commit_filename_matches = re.finditer(commit_and_filename_regex,
                                                  blame_out, flags=re.M)

            # we assume that a (commit, filepath) pair can be the cause of
            # just one bug in a file, hence we put the pairs in a set
            buggy_commit_file_pairs = set()
            for match in commit_filename_matches:
                commit_hash, _line_n, file_path = match.groups()
                line_n = int(_line_n)

                # we iterate over all the lines of the file and add to the set
                # only the ones that were removed
                if any(start_line <= line_n <= end_line
                       for start_line, end_line in removed_lines_ranges):
                    buggy_commit_file_pairs.add((commit_hash, file_path))

            for commit_file_pair in buggy_commit_file_pairs:
                if commit_file_pair in struct:
                    bugs_info = struct[commit_file_pair]['bugs_info']

                    bugs_counters = bugs_info['counters']
                    bugs_lists = bugs_info['lists']

                    bugs_counters['dev_time_bugs'] += dev_time_bugs
                    bugs_counters['post_release_bugs'] += post_release_bugs
                    bugs_counters['bugs_induced_qty'] += bugs_induced_qty

                    bugs_lists['fix_commits_hashes'].append(commit['hash'])
                    bugs_lists['fix_commits_tstamps'].append(commit['tstamp'])

#########################################
# 4TH STEP ##############################
#########################################

with open('assignment2.csv', 'w', newline='') as csvfile:
    fieldnames = ['commit_hash',
                  'file_name',
                  'directory_name',
                  'commit_author',
                  'timestamp',
                  'line_contributors_total',
                  'line_contributors_minor',
                  'line_contributors_major',
                  'line_contributors_ownership',
                  'line_contributors_author',
                  'line_contributors_author_owner',
                  'commit_contributors_total',
                  'commit_contributors_minor',
                  'commit_contributors_major',
                  'commit_contributors_ownership',
                  'commit_contributors_author',
                  'commit_contributors_author_owner',
                  'bugs_induced_qty',
                  'post_release_bugs',
                  'dev_time_bugs',
                  'fix_commits_hash',
                  'fix_commits_timestamp']

    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',')

    writer.writeheader()

    for ((commit_hash, file_path), info) in struct.items():
        splitted_filepath = file_path.split('/')
        file_name = splitted_filepath[-1]
        directory_name = '/'.join(splitted_filepath[:-1])

        commit_author = info['author_email']
        timestamp = info['author_date']

        if 'line_metrics' in info:
            line_metrics = info['line_metrics']

            line_contributors_total = line_metrics['total_contributors']
            line_contributors_minor = line_metrics['minor_contributors']
            line_contributors_major = line_metrics['major_contributors']
            line_contributors_ownership =  \
                line_metrics['ownership_best_contributor']
            line_contributors_author = line_metrics['commit_author_ratio']
            line_contributors_author_owner = \
                line_metrics['commit_author_is_best_contributor']
        else:
            line_contributors_total, line_contributors_minor = '', ''
            line_contributors_major, line_contributors_ownership = '', ''
            line_contributors_author, line_contributors_author_owner = '', ''

        if 'commit_metrics' in info:
            commit_metrics = info['commit_metrics']

            commit_contributors_total = commit_metrics['total_contributors']
            commit_contributors_minor = commit_metrics['minor_contributors']
            commit_contributors_major = commit_metrics['major_contributors']
            commit_contributors_ownership =  \
                commit_metrics['ownership_best_contributor']
            commit_contributors_author = commit_metrics['commit_author_ratio']
            commit_contributors_author_owner = \
                commit_metrics['commit_author_is_best_contributor']
        else:
            commit_contributors_total, commit_contributors_minor = '', ''
            commit_contributors_major, commit_contributors_ownership = '', ''
            commit_contributors_author = ''
            commit_contributors_author_owner = ''

        bugs_info = info['bugs_info']

        if bugs_info['counters']['bugs_induced_qty'] > 0:
            bugs_counters = bugs_info['counters']
            bugs_lists = bugs_info['lists']

            bugs_induced_qty = bugs_counters['bugs_induced_qty']
            post_release_bugs = bugs_counters['post_release_bugs']
            dev_time_bugs = bugs_counters['dev_time_bugs']

            fix_commits_hash = '|'.join(bugs_lists['fix_commits_hashes'])
            fix_commits_timestamp = \
                '|'.join(bugs_lists['fix_commits_tstamps'])
        else:
            bugs_induced_qty = 0
            post_release_bugs, dev_time_bugs = '', ''
            fix_commits_hash, fix_commits_timestamp = '', ''

        writer.writerow({
            'commit_hash': commit_hash,
            'file_name': file_name,
            'directory_name': directory_name,
            'commit_author': commit_author,
            'timestamp': timestamp,
            'line_contributors_total': line_contributors_total,
            'line_contributors_minor': line_contributors_minor,
            'line_contributors_major': line_contributors_major,
            'line_contributors_ownership': line_contributors_ownership,
            'line_contributors_author': line_contributors_author,
            'line_contributors_author_owner': line_contributors_author_owner,
            'commit_contributors_total': commit_contributors_total,
            'commit_contributors_minor': commit_contributors_minor,
            'commit_contributors_major': commit_contributors_major,
            'commit_contributors_ownership': commit_contributors_ownership,
            'commit_contributors_author': commit_contributors_author,
            'commit_contributors_author_owner':
                commit_contributors_author_owner,
            'bugs_induced_qty': bugs_induced_qty,
            'post_release_bugs': post_release_bugs,
            'dev_time_bugs': dev_time_bugs,
            'fix_commits_hash': fix_commits_hash,
            'fix_commits_timestamp': fix_commits_timestamp
        })
