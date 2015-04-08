from bs4 import BeautifulSoup
import requests
import numpy as np
import cPickle,json,sys,os,re
import argparse,traceback,time
from collections import Counter,deque
from urlparse import urlparse,urljoin,urldefrag

bad_filenames=['login.html','admin.html']
acceptable_extensions=['.html','.htm','.php','.asp','.aspx','']
acceptable_schemes=['http']
headers={'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.89 Safari/537.36'}

def visible(element):
    if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
        return False
    elif re.match('<!--.*-->', element.string):
        return False
    return True

def generatepatterns(**kwargs):
    make_disjunction=lambda lst:'|'.join(map(re.escape,lst))
    patterns=[]
#    patterns.append("^.*\/({})$".format(make_disjunction(acceptable_extensions)))
    patterns.append("^({}).*$".format(make_disjunction(acceptable_schemes)))
    return patterns

def scrape(**kwargs):
    """
    scrape(url,patterns,maxdepth=1,verbose=0,timeout=None,cachefile=None,reset_cache=False)

    Keyword Arguments:
    url - url to start scraping from
    patterns - a list of regular expressions to match links against

    """
    rooturl,patterns,maxdepth,verbose=map(kwargs.get,'url,patterns,maxdepth,verbose'.split(','))

    __pagecache__ = readCache(kwargs.get('cachefile'),**kwargs)
    patterns.extend(generatepatterns())
    if verbose>3:
        print "Using patterns: {}".format(patterns)
    patterns=[re.compile(p,re.I) for p in patterns]
    history=set()
    targetlist=[]
    stack=deque([rooturl])
    adjdict = {rooturl:[]}
    depths={rooturl:0}
    errorpages=set()
    try:
        while stack:
            currnode = urljoin(rooturl,stack.popleft())
            currdepth = depths[currnode]
            if currnode in history:
                continue
            if not currnode in __pagecache__:
                try:
                    if verbose>0:
                        print "({}) FRESH NODE URL: {}".format(currdepth,currnode.encode('utf'))
                    page = requests.get(currnode,timeout=kwargs.get("timeout"),headers=headers)
                    text = page.text
                    __pagecache__[currnode] = text
                    # Extract target links from current node
                except requests.RequestException,e:
                    errorpages.add(currnode)
                    print "Connection error: {}".format(currnode)
                    continue
            else:
                text = __pagecache__[currnode]
                if verbose>1:
                    print "({}) CACHED NODE URL: {}".format(currdepth,currnode.encode('utf'))
            tree = BeautifulSoup(text,'lxml')
            # append link to home address and "defrag" (strip hashtag anchors)
            links=[urljoin(rooturl,urldefrag(x['href'])[0]) \
                    for x in tree.findAll('a',href=True)]

            # update list of visited nodes
            history.add(currnode)

            if currnode not in adjdict:
                adjdict[currnode] = []

            # add suitable neighbors to stack
            for link in links:
                parsedlink=urlparse(link)
                path,ext = os.path.splitext(parsedlink.path)
                path,filename = os.path.split(path.strip('/'))
                filename+=ext
                adjdict[currnode].append(link)
                patternmatch=[True if p.match(link) else False for p in patterns]
                patternmatch.append(ext in acceptable_extensions)
                patternmatch.append(filename not in bad_filenames)
                if not np.all(patternmatch):
                    continue
                if link not in history and link not in stack and currdepth+1<=maxdepth:
                    if verbose>2:
                        print "Link match: {}".format(link.encode('utf'))
                    stack.append(link)
                    depths[link]=currdepth+1
    except KeyboardInterrupt:
        print "Stopping..."
    except:
        print "Error occured"
        ERROR=True
        exc_info = sys.exc_info()
        if exc_info[0]:
            print exc_info
            print traceback.format_exc()
        if kwargs.get('debug'):
            import pdb;
            pdb.set_trace()
    # Prune webpages with no outgoing links
    for key in adjdict.keys():
        if not len(adjdict[key]):
            adjdict.pop(key)
    if kwargs.get('cachefile'):
        writeCache(__pagecache__,kwargs.get('cachefile'),**kwargs)
    return adjdict


def readCache(*args,**kwargs):
    """
    readCache(cachefile,resetcache=False,verbose=0)

    Reads a dictionary from a pkl file

    Parameter Explanations
    ----------------------
    reset_cache - returns an empty dictionary (note that this does not
                 modify the file on disk)

    """
    cachefile,=args
    verbose,resetcache = [kwargs.get(k,v) for k,v in [('verbose',0),('reset_cache',False)]]
    if not cachefile or resetcache:
        return {}
    if os.path.isfile(cachefile):
        with open(cachefile,'rb') as fp:
            __pagecache__ = cPickle.load(fp)
            if verbose>0:
                print "Loaded {} pages from cache file".format(len(__pagecache__))
    else:
        __pagecache__ = {}
    return __pagecache__

def writeCache(*args,**kwargs):
    """
    writeCache(obj,cachefile,verbose=0)

    Pickles obj to cachefile

    Parameters
    ---------
    obj - object to write

    """
    obj,cachefile, = args
    verbose = kwargs.get('verbose',0)
    if not cachefile:
        return
    try:
        with open(cachefile,'wb') as fp:
            cPickle.dump(obj,fp)
        if verbose>1:
            print "Successfully wrote to cachefile {}.".format(cachefile)
    except IOError,e:
        print "Failure to write cachefile to: {}. Found this message: {}".format(cachefile,e)


def generateTransitionMatrix(adjdict,normalizerows=True):
    nodemap=dict(zip(adjdict.keys(),np.arange(len(adjdict))))
    nodes=np.array([k for k in nodemap])
    adjmat=np.zeros((len(nodemap),len(nodes)))
    i=0
    slices=[]
    for node in nodemap:
        for node2 in adjdict[node]:
            if node2 not in nodemap:
                continue
            j=nodemap[node2]
            adjmat[i,j]+=1
        i+=1
    # remove states without transitions
    emptystates=[1]
    while any(emptystates)>0:
        emptystates = np.all(np.isnan(adjmat) | np.equal(adjmat, 0), axis=1)
        nodes = nodes[~emptystates]
        adjmat = adjmat[~emptystates,:][:,~emptystates]
    if normalizerows:
        adjmat = adjmat/adjmat.sum(axis=1,keepdims=True)
    return adjmat,nodes


def rankKeywords(pagelist,ssprobs,**kwargs):
    """
    rankKeywords(pagelist,ssprobs,keywords=[],**kwargs)

    If the `keywords` argument is left blank, this function can be used to scrape and rank n-grams

    Parameters
    ---------
    minletters - the minimum number of letters required for a word to be included in the n-gram
    ngram - the 'n' in 'n-gram'
    maxdisplay - the maximum number of keywords to output if 'verbose' is on

    """
    #Uses the code provided to search each url for each keyword and update
    #the dictionary according to the rank of each page rather than simply adding one
    __pagecache__=readCache(kwargs.get('cachefile'),**kwargs)
    maxdisplay = kwargs.get("maxdisplay",100)
    keywords=kwargs.get("keywords",[])
    keywordpatterns=[re.compile(r"\b{}\b".format(k),re.I) if isinstance(k,str) else k for k in keywords]
    keyworddict={}
    appearancedict={}
    for i in keywords:
        keyworddict[i] = 0.
        appearancedict[i] = []
    url_list=pagelist
    all_words={}

    minletters = kwargs.get('minletters',4)
    maxletters = 45
    numwords = kwargs.get('ngram',1)
    all_wordpattern=re.compile('(?={})'.format(' '.join([(r"\b(\w{%d,%d})\b"%(minletters,maxletters)) for x in xrange(numwords)])))
    for i,url in enumerate(url_list):
        if url in __pagecache__:
            text = __pagecache__[url]
        else:
            try:
                page = requests.get(url,timeout=kwargs.get('timeout'),headers=headers)
                text = page.text
                page.close()
            except requests.RequestException:
                continue
        bs=BeautifulSoup(text)
        text = ' '.join(bs.stripped_strings);#' '.join(filter(visible,bs.findAll(text=True)))
        if not keywordpatterns:
            for word in all_wordpattern.findall(text):
                if word not in all_words:
                    all_words[word]=0
                all_words[word] += 100*ssprobs[i]
        else:
            for p,pattern in zip(keywords,keywordpatterns):
                matches=pattern.findall(text)
                if not matches:
                    continue
                nummatches = len(matches)
                # scale by 100 to avoid decimation
                keyworddict[p] += 100*ssprobs[i]*nummatches
                appearancedict[p].append(url)
    if not keywordpatterns:
        keyworddict=all_words
    keyword_ranks = [(x,y) for x,y in sorted(keyworddict.items(), key=lambda item: item[1], reverse=True)]
    if numwords>1:
        keyword_ranks = [(' '.join(x),y) for x,y in keyword_ranks]
    if kwargs.get('verbose')>0:
        for i in range(min(maxdisplay,len(keyword_ranks))):
            print "%d: %s | %.4g" % (i+1, keyword_ranks[i][0], keyword_ranks[i][1])
        return keyword_ranks, appearancedict

def steadystate(transition_matrix):
    """
    Find the steady state probabilities of the markov chain described
    by `transition_matrix`.

    """
    eigvals,eigvecs=np.linalg.eig(transition_matrix.T)
    return np.real(eigvecs[:,0]/np.sum(eigvecs[:,0]))

def main(**kwargs):
    """
    Performs the following tasks:
    -Scrapes links into a transition matrix.
    -Determines the system's steady state probabiliti or resetcaches.
    -Weights occurance of profressor's names on each page in order to
    calculate a "score" for each kewords.

    Keyword arguments:
    home - url to begin scraping at
    cachefile - storage for adjacency list
    reset_cache - refreshes cache
    verbose

    """
    url_start = kwargs.get('home')
    patterns = kwargs.get('patterns')
    keywords=kwargs.get('keywords')
    returndict = {}
    tstart=time.clock()
    adjlist = scrape(url=url_start,**kwargs);
    elapsed=time.clock()-tstart
    returndict['adjlist']=adjlist
    if kwargs.get('verbose')>0:
        print "Done!"
        sys.stdout.write("(elapsed: {}) ".format(elapsed))
        print "Scraped {} pages".format(len(adjlist))
        print "Computing eigenvectors..."
    pagematrix,pagelist=generateTransitionMatrix(adjlist)
    tstart=time.clock()
    steadyprobs=steadystate(pagematrix)
    elapsed=time.clock()-tstart
    if kwargs.get('verbose')>0:
        sys.stdout.write("(elapsed: {}) ".format(elapsed))
        print 'Calculated steady state probabilities: '
        print steadyprobs
    if not kwargs['scrape_only']:
        kwargs.pop('reset_cache') # don't reset the cache twice
        if kwargs.get('verbose')>0:
            print 'Ranking...'
        if kwargs.get('verbose')>1:
            print 'Keywords... {}'.format(keywords)
        tstart=time.clock()
        rankings,appearances=rankKeywords(pagelist,steadyprobs,**kwargs)
        elapsed=time.clock()-tstart
        returndict['rankings']=rankings
        returndict['appearances']=appearances
        sys.stdout.write("(elapsed: {}) ".format(elapsed))
        print "Done!"
    return returndict

def parsearguments(args):
    descstr="""
    Scrapes links into a transition matrix, determines the system's steady
    state probabilities, then weights occurance of profressor's names on
    each page in order to calculate a "score" for each keyword.
    """

    mainParser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,description=descstr)
    mainParser.add_argument('home',type=str,help="the url to start at")
    mainParser.add_argument('keywords',type=str,default=None,nargs="?",help="file containing keywords to rank")
    mainParser.add_argument('-n','--ngram',default=1,type=int,help="ngram size to scrape if keywords are not probided")
    mainParser.add_argument('-m','--min-letters',default=1,type=int,help="minimum number of letters required to include a word into an ngram")
    mainParser.add_argument('-p','--patterns',type=str,help="a list of \
            regular expressions that will be matched against encountered \
            links to determine (in part) whether or not they should be \
            followed",nargs='*',default=[])
    mainParser.add_argument('-P','--patternfile',help="instead of reading the patterns from the command line, they will be read from the specified file",type=argparse.FileType('r'),default=None)
    mainParser.add_argument('-R','--reset-cache',action="store_true",default=False)
    mainParser.add_argument('-O','--output',type=argparse.FileType('w'),default="lastrun.json",help='file to store output contents to')
    mainParser.add_argument('-S','--scrape-only',default=False,action="store_true",help='forgoes keyword-ranking')
    mainParser.add_argument('-c','--cachefile',type=str,help="location of  file (used to store adj list).",default="__pagecache__.pkl")
    mainParser.add_argument('-d','--maxdepth',default=1,type=int,help="the maximum recursion level")
    mainParser.add_argument('-t','--timeout',default=None,type=float,help="max seconds to spend loading page before moving on")
    mainParser.add_argument('-v','--verbose',type=int,default=0,help="set verbosity level (0 and up)")
    mainParser.add_argument('--debug',action='store_true',default=False,help="debug mode")
    parsedargs = mainParser.parse_args(args)
    if re.match('^file:.*',parsedargs.keywords):
        keywordsfile=parsedargs.keywords
        parsedargs.keywords = open(keywordsfile).readlines()
    else:
        parsedargs.keywords = parsedargs.keywords.split(',')
    parsedargs.keywords=[m.strip() for m in parsedargs.keywords]
    if parsedargs.patternfile!=None:
        parsedargs.patterns=[p.strip() for p in parsedargs.patternfile if p.strip()[0]!="#"]
    if parsedargs.verbose>0:
        print parsedargs
    return parsedargs

if __name__=="__main__":
    parsedargs = parsearguments(sys.argv[1:])
    result = main(**vars(parsedargs))
    # print results to stdout
    if parsedargs.output:
        json.dump(result,parsedargs.output,indent=2)
        parsedargs.output.close()
