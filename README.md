# Markov Rank
```
usage: makegraph.py [-h] [--keywords KEYWORDS] [--keywords-file KEYWORDS_FILE]
                    [-n NGRAM] [-m MIN_LETTERS] [-D]
                    [-p [PATTERNS [PATTERNS ...]]] [-P PATTERNFILE] [-R]
                    [-O OUTPUT] [-S] [-c CACHEFILE] [-d MAXDEPTH] [-t TIMEOUT]
                    [-v VERBOSE] [--debug]
                    home

Scrapes links into a transition matrix, determines the system's steady state
probabilities, then weights occurance of profressor's names on each page in
order to calculate a "score" for each keyword.

positional arguments:
  home                  the url to start at

optional arguments:
  -h, --help            show this help message and exit
  --keywords KEYWORDS   comma-separated list of keywords to rank (default:
                        None)
  --keywords-file KEYWORDS_FILE
                        keywords file (default: None)
  -n NGRAM, --ngram NGRAM
                        ngram size to scrape if keywords are not probided
                        (default: 1)
  -m MIN_LETTERS, --min-letters MIN_LETTERS
                        minimum number of letters required to include a word
                        into an ngram (default: 1)
  -D, --restrict-domain
                        don't crawl outside the original domain (default:
                        False)
  -p [PATTERNS [PATTERNS ...]], --patterns [PATTERNS [PATTERNS ...]]
                        a list of regular expressions that will be matched
                        against encountered links to determine (in part)
                        whether or not they should be followed (default: [])
  -P PATTERNFILE, --patternfile PATTERNFILE
                        instead of reading the patterns from the command line,
                        they will be read from the specified file (default:
                        None)
  -R, --reset-cache
  -O OUTPUT, --output OUTPUT
                        file to store output contents to (default:
                        lastrun.json)
  -S, --scrape-only     forgoes keyword-ranking (default: False)
  -c CACHEFILE, --cachefile CACHEFILE
                        location of file (used to store adj list). (default:
                        __pagecache__.pkl)
  -d MAXDEPTH, --maxdepth MAXDEPTH
                        the maximum recursion level (default: 1)
  -t TIMEOUT, --timeout TIMEOUT
                        max seconds to spend loading page before moving on
                        (default: None)
  -v VERBOSE, --verbose VERBOSE
                        set verbosity level (0 and up) (default: 0)
  --debug               debug mode (default: False)
  ```
