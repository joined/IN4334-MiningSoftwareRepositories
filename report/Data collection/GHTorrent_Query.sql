​-- Query used to obtain the list of Java projects maintained by
-- the Apache Software Foundation from http://ghtorrent.org/dblite/
SELECT *
FROM   projects ​where language = 'Java'
AND    owner_id =
       (
              SELECT id
              FROM   users
              WHERE  login = 'apache');