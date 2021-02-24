"""
Implements a sample streaming class for a BIDS archive

NOTE: This is prototype code for testing purposes, and not intended to serve as
production code. It has been neither rigorously tested nor particularly
carefully designed.
"""
import os
from rtCommon.bidsArchive import BidsArchive
import time
from projects.OpenNeuroSample.OpenNeuroProto import OpenNeuroOverview
from projects.OpenNeuroSample.OpenNeuroUpdate import OpenNeuroUpdate
from rtCommon.dicomToBidsService import dicomToBidsinc, dicomDirToBidsinc
defaultPath = '/Users/cocozhao/Documents/GitHub/rt-cloud/projects/openNeuroClient/'

class bidsStreamer():
    # the default path need to change to the path in cloud
    def __init__(self, datasetName, requiredMetadata, datasetType, sliceIndex:int = -1,
                 path:str = defaultPath):
        self.metadata = requiredMetadata
        self.datasetName = datasetName
        self.path = os.path.join(path, datasetName)
        self.dataset = BidsArchive(path) # the default dataset
        self.index = sliceIndex
        self.type = datasetType

    def get_next_image(self, definedIndex:int = 0):
        if definedIndex != 0:
            self.index = definedIndex - 1
        self.index += 1
        if self.type == 'archive':
            required_metadata = self.metadata
            self.dataset = BidsArchive(self.path)
            return self.dataset.getIncremental(
                    sliceIndex=self.index,
                    **required_metadata
                    )

        elif self.type == 'openNeuro':
            try:
                self.dataset = BidsArchive(self.path)
                required_metadata = self.metadata
                return self.dataset.getIncremental(
                    sliceIndex=self.index,
                    **required_metadata
                )
            except:
                input = self.path,self.metadata, "sub"
                self.dataset = OpenNeuroUpdate(input)
                return self.dataset.dataset_Bidsinc(sliceIndex=self.index)[0]
        elif self.type == 'dicom':
            return self.dataset
        elif self.type == 'dicomDir':
            return self.dataset[self.index]

def dicomMetadataSample() -> dict:
    sample = {}
    sample["ContentDate"] = "20190219"
    sample["ContentTime"] = "124758.653000"
    sample["RepetitionTime"] = 1500
    sample["StudyDescription"] = "Norman_Mennen^5516_greenEyes"
    sample["StudyInstanceUID"] = \
        "1.3.12.2.1107.5.2.19.45031.30000019021215313940500000046"
    sample["ProtocolName"] = "func_ses-01_task-faces_run-01"
    return sample
