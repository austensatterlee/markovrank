from bs4 import BeautifulSoup
import requests
import numpy as np
import cPickle,argparse,time
from collections import Counter
from collections import deque
import sys,traceback,os,re
from urlparse import urlparse,urljoin,urldefrag

bad_urls = ['http://bgess.berkeley.edu/%7Ensbejr/index.html','http://superior.berkeley.edu/Berkeley/Buildings/soda.html','http://physicalplant.berkeley.edu/','http://www.eecs.berkeley.edu/Deptonly/Rosters/roster.room.cory.html',' http://www.eecs.berkeley.edu/Resguide/admin.shtml#aliases','http://www.eecs.berkeley.edu/department/EECSbrochure/c1-s3.html']
bad_filenames=['login.html','admin.html']
acceptable_extensions=['.html','.htm','.php','.asp','.aspx','']
acceptable_schemes=['http']

def scrape(**kwargs):
    """
    Usage:

        scrape(url,patterns[,maxdepth=1][,verbose=0])

    Keyword Arguments:
    url
    patterns

    """
    rooturl,patterns,maxdepth,verbose=map(kwargs.get,'url,patterns,maxdepth,verbose'.split(','))

    __pagecache__ = readCache(kwargs.get('cachefile'),kwargs.get('reset_cache'))
    patterns=map(re.compile,patterns)
    history=set()
    targetlist=[]
    stack=deque([rooturl])
    adjdict = {rooturl:[]}
    depths={rooturl:0}
    try:
        while stack:
            currnode = urljoin(rooturl,stack.popleft())
            currdepth = depths[currnode]
            if currnode in history:
                continue
            if verbose>0:
                print "({}) NODE URL: {}".format(currdepth,currnode)
            if not currnode in __pagecache__:
                try:
                    page = requests.get(currnode)
                    # Extract target links from current node
                    tree = BeautifulSoup(page.text,'lxml')
                    links=[urljoin(rooturl,urldefrag(x['href'])[0]) for x in tree.findAll('a',href=True)]
                except requests.ConnectionError:
                    errorpages.add(currnode)
                    print "Connection error: {}".format(currnode)
                    continue
            else:
                links=__pagecache__[currnode]


            for link in links:
                if not all([p.match(link) for p in patterns]):
                    continue
                else:
                    targetlist.append(link)
                    if verbose>1:
                        print "Link match: ",link
            # update list of visited nodes
            history.add(currnode)

            if currnode not in adjdict:
                adjdict[currnode] = []

            # add suitable neighbors to stack
            for link in links:
                if link not in adjdict[currnode]:
                    adjdict[currnode].append(link)
                patternmatch=[p.match(link) for p in patterns]
                if link not in history and all(patternmatch) and currdepth+1<=maxdepth:
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
        if kwargs.get('cachefile'):
            writeCache(adjdict,kwargs.get('cachefile'))
    return adjdict


def readCache(cachefile,resetcache,verbose=0):
    if not cachefile or resetcache:
        return {}
    if os.path.isfile(cachefile):
        with open(cachefile,'rb') as fp:
            __pagecache__ = cPickle.load(fp)
            if verbose>0:
                print "Loaded graph of {} vertices from cache file".format(len(__pagecache__))
    else:
        __pagecache__ = {}
    return __pagecache__

def writeCache(__pagecache__,cachefile,verbose=1):
    if not cachefile:
        return
    try:
        with open(cachefile,'wb') as fp:
            cPickle.dump(__pagecache__,fp)
        if verbose>1:
            print "Successfully to write cachefile to: {}.".format(cachefile)
    except IOError,e:
        print "Failure to write cachefile to: {}. Found this message: {}".format(cachefile,e)


def generateTransitionMatrix(adjdict):
    nodes=dict(zip(adjdict.keys(),np.arange(len(adjdict))))
    adjmat=np.zeros((len(nodes),len(nodes)))
    i=0
    slices=[]
    for node in nodes:
        for node2 in adjdict[node]:
            if node2 not in nodes:
                continue
            j=nodes[node2]
            adjmat[i,j]=1
        i+=1
    emptystates=~np.all(adjmat == 0, axis=1)
    adjmat = adjmat[emptystates,:][:,emptystates]
    return adjmat/adjmat.sum(axis=1,keepdims=True)

def rankProfessors(adjlist,ssprobs,keywords,**kwargs):
    #Uses the code provided to search each url for each professor and update
    #the dictionary according to the rank of each page rather than simply adding one
    profs=keywords
    profdict={}
    for i in profs:
        profdict[i] = 0.
    url_list=adjlist.keys()
    for url in url_list:
        page = requests.get(url)
        text = page.text
        page.close()
        for p in profs:
            profdict[p] += ssprobs[url_list.index(url)] if " " + p + " " in text else 0
        #for p in profs:
            #profdict[p] += ssprobs[url_list.index(url)] if re.search("\b{}\b".format(p),text,re.I) else 0
    prof_ranks = [pair for pair in sorted(profdict.items(), key=lambda item: item[1], reverse=True)]
    if kwargs.get('verbose')>0:
        for i in range(len(prof_ranks)):
            print "%d: %s" % (i+1, prof_ranks[i])
    return prof_ranks

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
    calculate a "score" for each professor.

    Keyword arguments:
    home - url to begin scraping at
    cachefile - storage for adjacency list
    reset_cache - refreshes cache
    verbose

    """
    url_start = kwargs.get('home')
    patterns = kwargs.get('patterns')
    keywords=kwargs.get('keywords')
    tstart=time.clock()
    adjlist = scrape(url=url_start,**kwargs);
    elapsed=time.clock()-tstart
    if kwargs.get('verbose')>0:
        print "Done!"
        print "Scraped {} pages in {} seconds".format(len(adjlist),elapsed)
        print "Computing eigenvectors..."
    pagematrix=generateTransitionMatrix(adjlist)
    result=steadyprobs=steadystate(pagematrix)
    if kwargs.get('verbose')>0:
        print 'Calculated steady state probabilities: '
        print steadyprobs
    if not kwargs['scrape_only']:
        if kwargs.get('verbose')>0:
            print 'Ranking...'
        if kwargs.get('verbose')>1:
            print 'Keywords... {}'.format(keywords)
        result=rankProfessors(adjlist,steadyprobs,**kwargs)
    return result

def parsearguments(args):
    descstr="""
    Scrapes links into a transition matrix, determines the system's steady
    state probabilities, then weights occurance of profressor's names on
    each page in order to calculate a "score" for each professor.
    """

    mainParser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,description=descstr)
    mainParser.add_argument('keywords',type=argparse.FileType('r'),default=sys.stdin,help="file containing keywords to rank")
    mainParser.add_argument('-H','--home',type=str,help="the url to start at",default="http://www.eecs.berkeley.edu/Research/Areas/")
    mainParser.add_argument('-p','--patterns',type=str,help="a list of regular expressions that will be matched against encountered links to determine (in part) whether or not they should be followed",default=[".*\.eecs.berkeley.edu/.*"])
    mainParser.add_argument('-P','--patternfile',help="instead of reading the patterns from the command line, they will be read from the specified file",type=argparse.FileType('r'),default=None)
    mainParser.add_argument('-R','--reset-cache',action="store_true",default=False)
    mainParser.add_argument('-O','--output',type=argparse.FileType('w'),default=sys.stdout,help='file to store output contents to')
    mainParser.add_argument('-S','--scrape-only',default=False,action="store_true",help='forgoes professor-ranking')
    mainParser.add_argument('-c','--cachefile',type=str,help="location of cache file (used to store adj list)",default="__pagecache__.pkl")
    mainParser.add_argument('-d','--maxdepth',default=1,type=int,help="the maximum recursion level")
    mainParser.add_argument('-v','--verbose',type=int,default=0,help="set verbosity level (0 and up)")
    parsedargs = mainParser.parse_args(args)
    keywordsfile=parsedargs.keywords
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
    if 'output' in parsedargs:
        for r in result:
            parsedargs.output.write("{}\n".format(r))
    parsedargs.output.close()
