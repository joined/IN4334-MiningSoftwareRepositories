import sh
import pprint
import re
import requests
import csv
from collections import Counter, defaultdict

git = sh.git.bake(_cwd='lucene-solr')

# we are interested only in Java files inside the core
core_regex = r'^lucene\/core\/src\/java\/org\/apache\/lucene.*?\.java$'

#########################################
# 1ST STEP ##############################
#########################################

print("# Started 1st step")

start_date = "2013-01-01 00:00"
end_date = "2013-12-31 23:59"

log_output = str(git('--no-pager', 'log', '--name-only',
                     after=start_date, before=end_date,
                     pretty="format:[%H,%ai,%ae]"))

splitted_output = (s.split('\n') for s in log_output.split('\n\n'))

struct = {}

counter_1a = 0
for commit_group in splitted_output:
    print("Counter 1a: {}".format(counter_1a))
    counter_1a += 1

    i = 0

    # filter out empty commits, that appear on top of each group
    while commit_group[i+1][0] == '[' and commit_group[i+1][-1] == ']':
        i += 1

    commit_info = commit_group[i][1:-1]  # remove parenthesis at start and end
    commit_hash, author_date, author_email = commit_info.split(',')

    changed_files = commit_group[i+1:]
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
    total_contributors = len(counter)
    total_value = sum(counter.values())

    minor_contributors = sum(1 for author, value in counter.items()
                             if value/total_value <= 0.05)
    major_contributors = sum(1 for author, value in counter.items()
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

# Line contributors metrics computation
counter_1b = 0
for ((commit_hash, file_path), info) in struct.items():
    print("Counter 1b: {}".format(counter_1b))
    counter_1b += 1

    try:
        blame_out = str(
            git('--no-pager', 'blame', file_path, commit_hash + '^1',
                '--line-porcelain').stdout)
    except sh.ErrorReturnCode_128:
        # the file was not found at that specific commit, meaning that it still
        # didn't exist. in this case we leave the line metrics empty
        continue

    authors = re.findall(r'author-mail <(.+?@.+?\..+?)>',
                         blame_out, flags=re.M)
    authors_counter = Counter(authors)

    info['line_metrics'] = computeMetrics(authors_counter,
                                          info['author_email'])

#########################################
# 2ND STEP ##############################
#########################################

print("# Started 2nd step")

# Commit contributors metrics computation
start_date = "2011-01-01 00:00"

counter_2 = 0
for ((commit_hash, file_path), info) in struct.items():
    print("Counter 2: {}".format(counter_2))
    counter_2 += 1

    end_date = info['author_date']
    authors = git('--no-pager', 'log', '--after="%s"' % start_date,
                  '--before=%s' % end_date, '--pretty=%ae', '--',
                  file_path)
    if authors == '':
        continue

    splitted_authors = authors.split('\n')[:-1]  # last item is an empty string
    authors_counter = Counter(splitted_authors)

    info['commit_metrics'] = computeMetrics(authors_counter,
                                            info['author_email'])

#########################################
# 3RD STEP ##############################
#########################################

print("# Started 3rd step")

start_date = "2013-01-01 00:00"
end_date = "2016-01-01 00:00"

raw_revlist_output = git('rev-list', 'master', '--timestamp', pretty='oneline',
                         after=start_date, before=end_date)

commits_3rd_step = ({'title': commit[52:],
                     'hash': commit[11:40],
                     'tstamp': commit[:10]}
                    for commit in raw_revlist_output.split('\n')[:-1])

jira_bugs_json_url = 'https://issues.apache.org/jira/rest/api/2/search?jql='\
                     'project%20%3D%20LUCENE%20AND%20issuetype%20%3D%20Bug'\
                     '%20ORDER%20BY%20priority%20DESC'

jira_bugs_json = requests.get(jira_bugs_json_url).json()

bugs_issue_ids = []
for issue in jira_bugs_json['issues']:
    bugs_issue_ids.append(issue['key'])

print(bugs_issue_ids)

counter_3 = 0
for commit in commits_3rd_step:
    print("Counter 3: {}".format(counter_3))
    counter_3 += 1

    i += 1
    post_release_bug, dev_time_bug = 0, 0

    jira_match = re.search(r'LUCENE-\d{1,4}', commit['title'])

    if jira_match and jira_match.group() in bugs_issue_ids:
        post_release_bug = 1

    keywords = ('error', 'bug', 'fix', 'issue', 'mistake', 'incorrect',
                'fault', 'defect', 'flaw', 'typo')

    if any(keyword in commit['title'] for keyword in keywords):
        dev_time_bug = 1

    bugs_induced_qty = dev_time_bug + post_release_bug

    if bugs_induced_qty > 0:
        changed_files = git('--no-pager', 'show', '--name-only', '--pretty=',
                            commit['hash']).split('\n')[:-1]

        changed_files = filter(lambda f: re.search(core_regex, f),
                               changed_files)

        for file_path in changed_files:
            # after getting the list of files changed by the commit that
            # we know that fixes some bugs, we need to know for each file
            # which lines were removed, since we assume that those lines
            # contained the bug
            raw_show_output = str(git('--no-pager', 'show', '--no-color',
                                      '--format=', '--unified=0',
                                      commit['hash'], '--', file_path))

            removed_linenumbers_regex = \
                r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@'

            removed_lines_matches = re.finditer(removed_linenumbers_regex,
                                                raw_show_output, flags=re.M)

            removed_lines_ranges = []
            for match in removed_lines_matches:
                _start_line, _n_lines = match.groups()
                start_line = int(_start_line)
                n_lines = int(_n_lines) if _n_lines is not None else 1

                if n_lines != 0:
                    end_line = start_line + n_lines \
                        if n_lines \
                        else start_line

                    removed_lines_ranges.append((start_line, end_line))

            try:
                blame_out = str(
                    git('--no-pager', 'blame', '--line-porcelain',
                        commit['hash'] + '^1', '--', file_path))
            except sh.ErrorReturnCode_128:
                continue  # file didn't exist at the time of that commit

            commit_and_filename_regex = \
                r'^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?(?:\n.*?)+?filename (.+?)$'

            commit_filename_matches = re.finditer(commit_and_filename_regex,
                                                  blame_out, flags=re.M)

            # we assume that a <commit, filepath> pair can be the cause of
            # just one bug in a file
            buggy_commit_file_pairs = set()
            for match in commit_filename_matches:
                commit_hash, _line_n, file_path = match.groups()
                line_n = int(_line_n)

                if any(start_line <= line_n <= end_line
                       for start_line, end_line in removed_lines_ranges):
                    buggy_commit_file_pairs.add((commit_hash, file_path))

            for commit_file_pair in buggy_commit_file_pairs:
                if commit_file_pair in struct:
                    bugs_info = struct[commit_file_pair]['bugs_info']

                    bugs_counters = bugs_info['counters']
                    bugs_lists = bugs_info['lists']

                    bugs_counters['dev_time_bug'] += 1
                    bugs_counters['post_release_bug'] += 1
                    bugs_counters['bugs_induced_qty'] += 1

                    bugs_lists['fix_commits_hashes'] += commit['hash']
                    bugs_lists['fix_commits_tstamps'] += commit['tstamp']

#########################################
# 4TH STEP ##############################
#########################################

print("# Started 4th step")

with open('datacollection.csv', 'w', newline='') as csvfile:
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

    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')

    writer.writeheader()

    counter_4 = 0
    for ((commit_hash, file_path), info) in struct.items():
        print("Counter 4: {}".format(counter_4))
        counter_4 += 1

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

            fix_commits_hash = ','.join(bugs_lists['fix_commits_hashes'])
            fix_commits_timestamp = \
                ','.join(bugs_lists['fix_commits_timestamp'])
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
