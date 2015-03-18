import re, sys, os, urllib, urlparse, requests, time
from bs4 import BeautifulSoup
import numpy as np
import matplotlib.pyplot as plt
import cPickle

def domain(url,**kwargs):
    """
    This function will parse a url to give you the domain. Test it!
    urlparse breaks down the url passed it, and you split the hostname up
    #Ex: hostname="www.google.com" becomes ['www', 'google', 'com']

    """
    try:
        hostname = urlparse.urlparse(url).hostname
        if not hostname:
            return ""
        components = hostname.split('.')[-2:]
        if len(components)>=2:
            hostname = '.'.join(components[-2:])
        elif len(components)>=1:
            hostname = components[0]
        else:
            hostname = ""
    except StandardError,e:
        if kwargs.get('verbose')>0:
            print "Error when parsing domain {}: {}".format(url,e)
        hostname = ""
    return hostname

def parse_links(url, url_start,**kwargs):
    """
    This function will return all the urls on a page, and return the start url if there is an error or no urls

    """
    url_list = []
    page = None
    start_domain = domain(url, **kwargs)
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
            okay=domain(linkurl,**kwargs)==start_domain
            #we want to stay in the berkeley domain. This becomes more relevant later
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

    bad_urls = ['http://bgess.berkeley.edu/%7Ensbejr/index.html','http://superior.berkeley.edu/Berkeley/Buildings/soda.html','http://physicalplant.berkeley.edu/','http://www.eecs.berkeley.edu/Deptonly/Rosters/roster.room.cory.html',' http://www.eecs.berkeley.edu/Resguide/admin.shtml#aliases','http://www.eecs.berkeley.edu/department/EECSbrochure/c1-s3.html']
    #special implementation of DFS where I give it a page and I return
    # a list of all verticies in the graph
    maxdepth=kwargs.get('maxdepth')
    cachefile=kwargs.get('cachefile')
    resetcache=kwargs.get('reset_cache')
    verbose = kwargs.get('verbose')
    __pagecache__ = readCache(cachefile,verbose)

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
                if not kwargs.get('resetcache') and vertex in __pagecache__:
                    links=__pagecache__[vertex]
                else:
                    links=parse_links(vertex, url_start,**kwargs)
                for url in links:
                    # Checks to make sure it is not a bad page
                    if (depth>=maxdepth and maxdepth!=None) or url in bad_urls or "iris" in url or "Deptonly" in url:
                        pass
                    else:
                        depthmap[url]=depth+1
                        stack.append(url)
                        visited[vertex].add(url)
            except StandardError,e:
                if kwargs.get('verbose')>0:
                    print "Error {} on {}".format(e,vertex)
                continue
            __pagecache__[vertex]=visited[vertex]
            i+=1
            if kwargs.get('verbose')>1:
                #progress output
                sys.stdout.write('\b'*len(statusstr))
                sys.stdout.flush()
                statusstr='Depth: {:5d}, Iteration: {:5d}, Visiting... {:50s}'.format(depth,i,vertex)
                sys.stdout.write(statusstr)

    except KeyboardInterrupt:
        pass
    if kwargs.get('verbose')>0:
        print "#Vertices: %d"%len(visited)
        print "#Edges:    %d"%len(visited.values())
    sys.stdout.flush()
    writeCache(__pagecache__,cachefile,verbose)
    return visited

def readCache(cachefile,verbose=0):
    if not cachefile:
        return {}
    if os.path.isfile(cachefile):
        with open(cachefile,'rb') as fp:
            __pagecache__ = cPickle.load(fp)
            if verbose>0:
                print "Loaded graph of {} vertices from cache file".format(len(__pagecache__))
    else:
        __pagecache__ = {}
    return __pagecache__

def writeCache(__pagecache__,cachefile,verbose=0):
    if not cachefile:
        return
    try:
        with open(cachefile,'wb') as fp:
            cPickle.dump(__pagecache__,fp)
        if verbose>1:
            print "Successfully to write cachefile to: {}.".format(cachefile)
    except IOError,e:
        if verbose>0:
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

def main(**kwargs):
    url_start = kwargs.get("home")
    tstart=time.clock()
    adjlist = dfs(url_start,**kwargs);
    elapsed=time.clock()-tstart
    if kwargs.get('verbose')>0:
        print "Done!"
        print "Scraped {} pages in {} seconds".format(len(adjlist),elapsed)
    pagematrix=generateTransitionMatrix(adjlist,**kwargs)
    return pagematrix

if __name__=="__main__":
    import argparse
    args = sys.argv[1:]
    mainParser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    mainParser.add_argument('-H','--home',type=str,help="the url to start at",default="http://www.eecs.berkeley.edu/Research/Areas/")
    mainParser.add_argument('-c','--cachefile',type=str,help="location of cache file (used to store adj list)",default="__pagecache__.pkl")
    mainParser.add_argument('-R','--reset-cache',action="store_true",default=False)
    mainParser.add_argument('-d','--maxdepth',default=1,type=int,help="the maximum recursion level")
    mainParser.add_argument('-v','--verbose',type=int,default=0,help="set verbosity level (0 and up)")
    mainParser.set_defaults(func=main)

    argstr = ' '.join(args)
    parsedargs = mainParser.parse_args()
    if parsedargs.verbose>0:
        print parsedargs
    result = parsedargs.func(**vars(parsedargs))
    # print results to stdout
    for r in result:
        sys.stdout.write("{}\n".format(r))
