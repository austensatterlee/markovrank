import re, sys, os, urllib, urlparse, requests, time
import multiprocessing as mp
from bs4 import BeautifulSoup
import numpy as np
import matplotlib.pyplot as plt
import cPickle


#This function will parse a url to give you the domain. Test it!
def domain(url):
    #urlparse breaks down the url passed it, and you split the hostname up 
    #Ex: hostname="www.google.com" becomes ['www', 'google', 'com']
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
        print e,url
        hostname = ""
    return hostname
    
#Move list above so I can use it for the ranking professors function
url_list = []

#This function will return all the urls on a page, and return the start url if there is an error or no urls
def parse_links(url, url_start):
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
            okay=domain(linkurl).endswith('berkeley.edu')
            #we want to stay in the berkeley domain. This becomes more relevant later
            if okay:
                url_list.append(linkurl)
        if len(url_list) == 0:
            return [url_start]
        return url_list
    except IOError,e:
        printprint [page,e]
        return 

def dfs(url_start,depthmax=None,resetcache=False,cachefile=None):
    bad_urls = ['http://bgess.berkeley.edu/%7Ensbejr/index.html','http://superior.berkeley.edu/Berkeley/Buildings/soda.html','http://physicalplant.berkeley.edu/','http://www.eecs.berkeley.edu/Deptonly/Rosters/roster.room.cory.html',' http://www.eecs.berkeley.edu/Resguide/admin.shtml#aliases','http://www.eecs.berkeley.edu/department/EECSbrochure/c1-s3.html']
    __pagecache__ = readCache(cachefile)
    #special implementation of DFS where I give it a page and I return
    # a list of all verticies in the graph
    visited,stack={},[url_start]
    i=0
    try:
        while stack:
            vertex = stack.pop()
            if vertex in visited or (len(stack)>depthmax and depthmax!=None):
                continue
            #loop over all the pages that my current page connects to
            if not resetcache and vertex in __pagecache__:
                visited[vertex]=__pagecache__[vertex]
                stack.extend(visited[vertex])
            else:
                visited[vertex]=set()
                try:                
                    links=parse_links(vertex, url_start)
                    for url in links:
                        # Checks to make sure it is not a bad page
                        if url in bad_urls or "iris" in url or "Deptonly" in url:
                            pass
                        else:
                            stack.append(url)
                            visited[vertex].add(url)
                except StandardError,e:
                    print "Error {} on {}".format(e,vertex)
                    continue                
                __pagecache__[vertex]=visited[vertex]
            i+=1
    except KeyboardInterrupt:
        pass
        # progress output
        #statusstr='Depth: {:5d}, Iteration: {:5d}, Visiting... {:50s}\n'.format(len(stack),i,vertex)
        #sys.stdout.write(statusstr)
        #sys.stdout.flush()
        #if i%2==0:
        #    clear_output()
    print "#Vertices: %d"%len(visited)
    print "#Edges:    %d"%len(visited.values())
    sys.stdout.flush()
    writeCache(__pagecache__,cachefile)
    return visited

def readCache(cachefile):
    if not cachefile:
        return {}
    if os.path.isfile(cachefile):
        with open(cachefile,'rb') as fp:
            __pagecache__ = cPickle.load(fp)
    else:
        __pagecache__ = {}
    return __pagecache__

def writeCache(__pagecache__,cachefile):
    if not cachefile:
        return
    with open(cachefile,'wb') as fp:
        cPickle.dump(__pagecache__,fp)


def generateTransitionMatrix(adjlist):
    num_pages=float(len(adjlist))
    pagematrix = np.zeros([num_pages,num_pages])
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

def stateMatrix(adjlist):
    #Uses the code provided to make the state matrix
    vals, vecs = np.linalg.eig(adjlist.T)
    return np.real(vecs[:,0]/sum(vecs[:,0]))



def rankProfessors(stateMatrix):
    #Uses the code provided to search each url for each professor and update
    #the dictionary according to the rank of each page rather than simply adding one
    profdict = {}
    for i in profs:
        profdict[i] = 0
    for url in url_list:
        myopener = MyOpener()
        page = myopener.open(current_url)
        text = page.read()
        page.close()
        for p in profs:
            profdict[p] += stateMatrix[0][url_list.index(url)] if " " + p + " " in text else 0
    prof_ranks = [pair[0] for pair in sorted(profdict.items(), key=lambda item: item[1], reverse=True)]
    for i in range(len(prof_ranks)):
        print "%d: %s" % (i+1, prof_ranks[i])



def main(**kwargs):
    url_start = kwargs.get("home")
    max_depth = kwargs.get("maxdepth")
    cachefile = kwargs.get("cachefile")
    tstart=time.clock()
    adjlist = dfs(url_start,max_depth,cachefile);
    steady_state = stateMatrix(adjlist);
    rankProfessors(steady_state);
    elapsed=time.clock()-tstart
    print "Done!"
    print "Scraped {} pages in {} seconds".format(len(adjlist),elapsed)
    pagematrix=generateTransitionMatrix(adjlist)
    return pagematrix

if __name__=="__main__":
    import argparse
    args = sys.argv[1:]
    mainParser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    mainParser.add_argument('-H','--home',type=str,help="the url to start at",default="http://www.eecs.berkeley.edu/Research/Areas/")
    mainParser.add_argument('-c','--cachefile',type=str,help="location of cache file (used to store adj list)",default="__pagecache__.pkl")
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