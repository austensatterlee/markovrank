import re, sys, os, urlparse, requests, time
from bs4 import BeautifulSoup
import numpy as np
#import matplotlib.pyplot as plt
import cPickle
import argparse

bad_urls = ['http://bgess.berkeley.edu/%7Ensbejr/index.html','http://superior.berkeley.edu/Berkeley/Buildings/soda.html','http://physicalplant.berkeley.edu/','http://www.eecs.berkeley.edu/Deptonly/Rosters/roster.room.cory.html',' http://www.eecs.berkeley.edu/Resguide/admin.shtml#aliases','http://www.eecs.berkeley.edu/department/EECSbrochure/c1-s3.html']
bad_filenames=['login.html','admin.html']
acceptable_extensions=['.html','.htm','.php','.asp','.aspx','']
acceptable_schemes=['http']

def verify_link(linkurl,url_start,**kwargs):
    """
    Applies a variety of tests to determine whether a link is safe

    """
    origurlparts = urlparse.urlparse(url_start)
    linkurlparts = urlparse.urlparse(linkurl)
    linkfilename = os.path.split(linkurlparts.path)[1]
    trace=[True]
    okay=linkurlparts.netloc==origurlparts.netloc
    trace.append(okay)
    okay&=linkurlparts.scheme in acceptable_schemes
    trace.append(okay)
    okay&=os.path.splitext(linkurl)[1] in acceptable_extensions
    trace.append(okay)
    okay&=not (linkurl in bad_urls or "iris" in linkurl or "Deptonly" in linkurl)
    trace.append(okay)
    okay&=linkfilename not in bad_filenames
    trace.append(okay)
    if kwargs.get('verbose')>2:
        print linkurl,trace
    return okay

def parse_links(url, url_start,**kwargs):
    """
    This function will return all the urls on a page, and return the start url if there is an error or no urls

    """
    url_list = []
    page = None
    try:
        #open, read, and parse the text using beautiful soup
        page = requests.get(url)
        text = page.text
        page.close()
        soup = BeautifulSoup(text,'lxml')

        #find all hyperlinks using beautiful soup
        for tag in soup.findAll('a', href=True):
            #concatenate the base url with the path from the hyperlink
            linkurl = urlparse.urljoin(url, tag['href'])
            linkurl = urlparse.urldefrag(linkurl)[0]
            #we want to stay in the berkeley domain. This becomes more relevant later
            okay=verify_link(linkurl,url_start,**kwargs)
            if okay:
                url_list.append(linkurl)
        if len(url_list) == 0:
            return [url_start]
        return url_list
    except IOError,e:
        if kwargs.get('verbose')>0:
            print "Error when scraping link on page {}: {}".format(page,e)
        return

def dfs(url_start,**kwargs):
    """
    Generate an adjacency list from the outgoing links on the given web page.

    Keyword arguments:
    maxdepth - limits the recursion limit of the graph search
    cachefile - specifies a filename to be used as a cache (to save time on large repeated calls)
    reset_cache - refreshes the cache by forcing each query to go to the web

    Returns a mapping from parent_url->list(child_urls).
    """

    #special implementation of DFS where I give it a page and I return
    # a list of all verticies in the graph
    maxdepth=kwargs.get('maxdepth')
    cachefile=kwargs.get('cachefile')
    resetcache=kwargs.get('reset_cache')
    verbose = kwargs.get('verbose')
    __pagecache__ = readCache(cachefile,resetcache,verbose)

    i=0
    depthmap = {url_start:0}
    visited,stack={},[url_start]
    statusstr=""
    if verbose>0:
        print "Max depth: {}, cachefile: {}, cache reset: {}".format(maxdepth,cachefile,resetcache)
    try:
        while stack:
            vertex = stack.pop()
            depth=depthmap[vertex]
            if vertex in visited:
                continue
            #loop over all the pages that my current page connects to
            visited[vertex]=set()
            try:
                if vertex in __pagecache__:
                    links=__pagecache__[vertex]
                else:
                    links=parse_links(vertex, url_start,**kwargs)
                for url in links:
                    # Checks to make sure it is not a bad page
                    if (depth>=maxdepth and maxdepth!=None):
                        pass
                    else:
                        depthmap[url]=depth+1
                        stack.append(url)
                        visited[vertex].add(url)
            except UnicodeWarning,e:
                if kwargs.get('verbose')>0:
                    print "Error {} on {}".format(e,vertex)
                continue
            i+=1
            if kwargs.get('verbose')>1:
                #progress output
                sys.stdout.flush()
                statusstr='Depth: {:5d}, Iteration: {:5d}, Visiting... {:>96}'.format(depth,i,vertex)
                statusstr=statusstr.zfill(200-len(statusstr))
                sys.stdout.write(statusstr)
                sys.stdout.write('\b'*len(statusstr))
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    if kwargs.get('verbose')>0:
        print "#Vertices: %d"%len(visited)
        print "#Edges:    %d"%len(visited.values())
    sys.stdout.flush()
    writeCache(visited,cachefile)
    return visited

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

def generateTransitionMatrix(adjlist,**kwargs):
    """
    Converts an adjacency list to an adjacency matrix,
    with the modification that each row sums to one.

    """
    num_pages=float(len(adjlist))
    pagematrix = np.zeros([num_pages,num_pages])
    if kwargs.get('verbose')>0:
        print 'Number of nodes: %d'%pagematrix.shape[0]
    for i,page in enumerate(adjlist):
        url_list = adjlist[page]
        url_list = set.intersection(url_list,adjlist)
        num_transitions=0
        for j,transitionpage in enumerate(adjlist):
            if transitionpage in url_list:
                pagematrix[i,j]=1
                num_transitions+=1

        if num_transitions>0:
            pagematrix[i]*=1./num_transitions
    return pagematrix

def rankProfessors(adjlist,ssprobs,keywords,**kwargs):
    #Uses the code provided to search each url for each professor and update
    #the dictionary according to the rank of each page rather than simply adding one
    if kwargs.get('cachefile')!=None:
        __cache__ = readCache('kwd'+kwargs.get('cachefile'))
        profdict = __cache__
    else:
        profdict = {}

    profs=keywords
    for i in profs:
        profdict[i] = 0
    url_list=adjlist.keys()
    for url in url_list:
        page = requests.get(url)
        text = page.text
        page.close()
        for p in profs:
            profdict[p] += ssprobs[url_list.index(url)] if re.search("\b{}\b".format(p),text)else 0
    prof_ranks = [pair[0] for pair in sorted(profdict.items(), key=lambda item: item[1], reverse=True)]
    if kwargs.get('verbose')>0:
        for i in range(len(prof_ranks)):
            print "%d: %s" % (i+1, prof_ranks[i])
    if cachefile!=None:
        cachefile="kwd"+kwargs.get('cachefile')
        writeCache(profdict,cachefile)
    return profdict

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
    url_start = kwargs.get("home")
    keywords=kwargs.get('keywords')
    tstart=time.clock()
    adjlist = dfs(url_start,**kwargs);
    elapsed=time.clock()-tstart
    if kwargs.get('verbose')>0:
        print "Done!"
        print "Scraped {} pages in {} seconds".format(len(adjlist),elapsed)
        print "Computing eigenvectors..."
    pagematrix=generateTransitionMatrix(adjlist,**kwargs)
    result=steadyprobs=steadystate(pagematrix)
    if kwargs.get('verbose')>0:
        print 'Calculated steady state probabilities: '
        print steadyprobs
    if not kwargs['scrape_only']:
        if kwargs.get('verbose')>0:
            print 'Ranking...'
        if kwargs.get('verbose')>1:
            print 'Keywords... {}'.format(keywords)
        result=rankProfessors(adjlist,steadyprobs,keywords,**kwargs)
    return result

def parsearguments(args):
    descstr="""
    Scrapes links into a transition matrix, determines the system's steady
    state probabilities, then weights occurance of profressor's names on
    each page in order to calculate a "score" for each professor.
    """

    mainParser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,description=descstr)
    mainParser.add_argument('keywords',type=argparse.FileType('r'),nargs='?',default=sys.stdin,help="file containing keywords to rank")
    mainParser.add_argument('-H','--home',nargs='?',type=str,help="the url to start at",default="http://www.eecs.berkeley.edu/Research/Areas/")
    mainParser.add_argument('-R','--reset-cache',action="store_true",default=False)
    mainParser.add_argument('-O','--output',type=argparse.FileType('w'),default=sys.stdout,help='file to store output contents to')
    mainParser.add_argument('-S','--scrape-only',default=False,action="store_true",help='forgoes professor-ranking')
    mainParser.add_argument('-c','--cachefile',type=str,help="location of cache file (used to store adj list)",default="__pagecache__.pkl")
    mainParser.add_argument('-d','--maxdepth',default=1,type=int,help="the maximum recursion level")
    mainParser.add_argument('-v','--verbose',type=int,default=0,help="set verbosity level (0 and up)")
    parsedargs = mainParser.parse_args(args)
    keywordsfile=parsedargs.keywords
    parsedargs.keywords=[m.strip() for m in parsedargs.keywords]
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
