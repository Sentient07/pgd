from django.conf.urls.defaults import *


from pgd_search.search.views import search, saved, editSearch, help, qtiphelp, saveSearch, deleteSearch
from pgd_search.plot.views import renderToSVG, renderToPNG, plotDump, plot
from pgd_search.statistics.views import searchStatistics
from pgd_search.dump.views import dataDump
from pgd_search.browse.views import browse

urlpatterns = patterns('',
    (r'^$', search),
    (r'^results/$', plot),
    (r'^plot/svg/$', plot),
    (r'^plot/svg/render/$', renderToSVG),
    (r'^plot/png/$', renderToPNG),
    (r'^plot/dump/$', plotDump),
    (r'^statistics/$', searchStatistics),
    (r'^dump/$', dataDump),
    (r'^browse/$', browse),
    (r'^saved/$', saved),
    (r'^help/$', help),
	(r'^qtiphelp/$', qtiphelp),
    (r'^viewSearch/$', editSearch),
    (r'^viewSearch/(?P<search_id>\d+)/$', editSearch),
    (r'^edit/$', editSearch),
    (r'^edit/(?P<search_id>\d+)/$', editSearch),
    (r'^saveSearch/$', saveSearch),
    (r'^saveSearch/(?P<search_id>\d+)/$', saveSearch),
    (r'^deleteSearch/$', deleteSearch),
    (r'^deleteSearch/(?P<search_id>\d+)/$', deleteSearch),
    
)
