#!/usr/bin/env python
if __name__ == '__main__':
    import sys
    import os

    #python magic to add the current directory to the pythonpath
    sys.path.append(os.getcwd())

    # ==========================================================
    # Setup django environment 
    # ==========================================================
    if not os.environ.has_key('DJANGO_SETTINGS_MODULE'):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
    # ==========================================================
    # Done setting up django environment
    # ==========================================================

import math

from pydra_server.cluster.tasks import Task
from pgd_core.models import *
from pgd_search.models import *

"""
Task that processes protein chains to create or update segment objects

This task requires that proteins, chains, and residues have already been created
"""
class SegmentBuilderTask(Task):

    proteinCount = None
    proteinTotal = None

    def _work(self, pdbs):

        length = searchSettings.segmentSize
        self.proteinCount = 0
        lastIndex = length - 1

        #calculate the position of i in an array of size 'length'
        iIndex = int(math.ceil(length/2.0)-1)

        #calculate offset of last index from iIndex
        lastIndexOffset = lastIndex - iIndex

        #determine if there are any segments in the table
        #   limit query with [0:0] instead of [0] this returns
        #   an empty list instead of an exception if there are no segments
        existingSegments = len(Segment.objects.filter(protein__in=pdbs)[0:1]) != 0

        if not existingSegments:
            print 'No Segments Found, skipping residue existence check for all residues'

        proteins = Protein.objects.filter(code__in=pdbs)
        self.proteinTotal = len(proteins)
        for protein in proteins:
            self.proteinCount += 1
            print 'protein (%d/%d) : %s' % (self.proteinCount, self.proteinTotal, protein.code)

            chains = protein.chains.all()
            for chain in chains:
                print '    chain: %s' % chain.code

                #setup initial list to have values where the first iteration of the list 
                #will be what is needed for processing the first residue
                segmentList = []

                #populate beginning of list with Nones
                for i in range(iIndex):
                    segmentList.append(None)

                #populate remaining residues with values looked up from the database
                id = 0
                for i in range(iIndex, length):
                    try:
                        residue = chain.residues.get(chainIndex=id)
                    except:
                        residue = None
                    segmentList.append(residue)
                    id = id + 1

                #determine index of the last known residue in the chain
                print '?????', chain
                result = chain.residues.order_by('chainIndex').reverse()[0]
                chainLength = result.chainIndex
                print '        chainlength: %s' % chainLength

                #iterate through all possible residue indexes for this chain
                for ri in range(1, chainLength+1):

                    #roll list to next possible segment
                    #  this will roll lastIndexOffset past the last known index but this is expected
                    #  the queries will return None which is also expected
                    #  the last known index will have a maximum length of 1 with all remaining residues as None
                    try:
                        residue = chain.residues.get(chainIndex=ri+lastIndexOffset)
                    except:
                        residue = None

                    segmentList.append(residue)
                    del segmentList[0]
                    #print '            list: %s' % segmentList

                    #if i is None, or it is a terminal residue then skip this segment
                    #its maxLength would be 0 and the segment would never be returned in any search
                    if not (segmentList[iIndex] and segmentList[iIndex-1] and segmentList[iIndex+1]) or segmentList[iIndex].terminal_flag:
                        continue

                    # Only check for existing version of the segment if there
                    # are records in the segment table (wasted cycles otherwise)
                    if existingSegments:
                        #find existing segment or create new one
                        iProperty = 'r%d_chainIndex' % iIndex
                        kwargs = {'protein__code':str(protein.code), iProperty:int(segmentList[iIndex].chainIndex)}
                        try:
                            segment = Segment.objects.get(**kwargs)

                        #an exception will be thrown if the segment doesnt exist
                        #ignore the exception and create a new Segment
                        except:
                            segment = Segment()
                    else:
                        segment = Segment()

                    #set residues in segment
                    #print segmentList
                    for i in range(length):
                        segment.residues[i] = segmentList[i]

                    segment.protein = protein
                    segment.chainID = chain.code

                    #calculate max length of this particular segment
                    #first, last, and any residue with terminal flag always have length 1
                    for i in range(1, length):
                        # have we reached the max size for segments or found a None
                        if iIndex+i > lastIndex or (segmentList[iIndex+i] and (segmentList[iIndex+i].terminal_flag or segmentList[iIndex+i].chainIndex==chainLength)):
                                segment.length = i*2-1
                                break
                        if iIndex-i < 0 or (segmentList[iIndex-i] and segmentList[iIndex-i].terminal_flag):
                                segment.length = i*2
                                break

                    #save segment
                    #print '            segment: %s' % segment
                    segment.save()


if __name__ == '__main__':
    import sys
    builder = SegmentBuilderTask('Command Line Builder')
    builder._work(**{'pdbs':sys.argv[1:]})
