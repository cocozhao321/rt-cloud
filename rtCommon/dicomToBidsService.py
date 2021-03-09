"""-----------------------------------------------------------------------------

dicomToBidsService.py

Eventually, this will implement conversion between DICOM and BIDS.

-----------------------------------------------------------------------------"""
from nibabel.pydicom_compat import pydicom

from rtCommon.bidsCommon import getDicomMetadata
from rtCommon.bidsIncremental import BidsIncremental
from rtCommon.imageHandling import convertDicomImgToNifti, readDicomFromFile


def dicomToBidsinc(dicomFile, requiredMetadata: {},datasetMetadata:{}) -> BidsIncremental:
    # TODO(spolcyn): Do this all in memory -- dicom2nifti is promising
    # Put extra metadata in sidecar JSON file
    # Currently, there are 4 disk operations:
    # 1) Read DICOM (by dcm2niix)
    # 2) Write NIfTI
    # 3) Read NIfTI
    # 4) Read DICOM (for metadata)

    # NOTE: This is not the final version of this method.
    # The conversion from DICOM to BIDS-I and gathering all required metadata
    # can be complex, as DICOM doesn't necessarily have the metadata required
    # for BIDS in it by default. Thus, another component will handle the logic
    # and error handling surrounding this.
    dicomImg = readDicomFromFile(dicomFile)
    niftiImage = convertDicomImgToNifti(dicomImg)
    #logger.debug("Nifti header after conversion is: %s", niftiImage.header)
    publicMeta, privateMeta = getDicomMetadata(dicomImg)
    publicMeta.update(privateMeta)  # combine metadata dictionaries
    publicMeta.update(requiredMetadata)
    return BidsIncremental(niftiImage,publicMeta, datasetMetadata)

def dicomDirToBidsinc(dicomDir, TR, requiredMetadata:{},datasetMetadata:{}):
    bidsinc_list = []
    scan = "13" # need to include in requiredMetadata or use different dicom filename format
    for i in range(TR+1):
        subject = requiredMetadata['subject'].zfill(3)
        scanNum = scan.zfill(6)
        num = str(i).zfill(6)
        dicomFile = dicomDir + "/" + "{}_{}_{}.dcm".format(subject, scanNum, num)
        bidsinc_list.append(dicomToBidsinc(dicomFile,requiredMetadata,datasetMetadata))
    return bidsinc_list
