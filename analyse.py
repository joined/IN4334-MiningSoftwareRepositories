#! /bin/sh
print('lol')
import sh
git = sh.git.bake(_cwd='lucene-solr')

shaFeb15 = (git("rev-list","-n 1","--before=\"2015-02-01 00:01\"","master")).stdout[:-1]
git.checkout(shaFeb15)

files = git("ls-tree", "-r", "master", "--name-only")
#lucene/tools/src/java/org/apache/lucene/validation/ivyde/IvyNodeElementAdapter.java


file_names = []
for file_name in files:
	file_name = file_name.strip('\n')
	if file_name.endswith(".java") and file_name.split('/')[0] == 'lucene':
		file_names.append(file_name)

