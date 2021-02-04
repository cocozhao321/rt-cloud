"""-----------------------------------------------------------------------------

bidsIncremental.py

Implements the BIDS Incremental data type used for streaming BIDS data between
different applications.

-----------------------------------------------------------------------------"""
from copy import deepcopy
import json
from operator import eq as opeq
import os
from typing import Any, Callable

from bids.layout.writing import build_path as bids_build_path
import logging
import nibabel as nib
import numpy as np
import pandas as pd

from rtCommon.errors import MissingMetadataError
from rtCommon.bidsCommon import (
    BidsFileExtension,
    BIDS_FILE_PATTERN,
    BIDS_DIR_PATH_PATTERN,
    DATASET_DESC_REQ_FIELDS,
    DEFAULT_DATASET_DESC,
    adjustTimeUnits,
    filterEntities,
    getNiftiData,
    loadBidsEntities,
    metadataFromProtocolName,
    symmetricDictDifference,
)

logger = logging.getLogger(__name__)


class BidsIncremental:
    ENTITIES = loadBidsEntities()
    REQUIRED_IMAGE_METADATA = ["subject", "task", "suffix", "datatype",
                               "RepetitionTime", "EchoTime"]

    """
    BIDS Incremental data format suitable for streaming BIDS Archives
    """
    def __init__(self,
                 image: nib.Nifti1Image,
                 imageMetadata: dict,
                 datasetMetadata: dict = None):
        """
        Initializes a BIDS Incremental object with provided image and metadata.

        Args:
            image: Nifti image as an NiBabel NiftiImage.
            imageMetadata: Metadata for image
            datasetMetadata: Top-level dataset metadata for the BIDS dataset
                to be placed in a dataset_description.json.

        Raises:
            MissingMetadataError: If any required metadata is missing.

        """

        """ Do basic input validation """
        # IMAGE
        if image is None or \
                (type(image) is not nib.Nifti1Image and
                 type(image) is not nib.Nifti2Image):
            raise TypeError("Image must be NIBabel Nifti 1 or 2 image, "
                            "got type %s" % str(type(image)))

        # DATASET METADATA
        if datasetMetadata is not None:
            missingFields = [field for field in DATASET_DESC_REQ_FIELDS
                             if datasetMetadata.get(field, None) is None]
            if missingFields:
                raise MissingMetadataError(
                    f"Dataset description needs: {str(missingFields)}")

        """ Store image metadata """
        self._preprocessAndSetMetadata(imageMetadata)
        self._assertHaveRequiredMetadata()
        self._postprocessMetadata()

        """ Store dataset metadata """
        if datasetMetadata is None:
            self.datasetMetadata = DEFAULT_DATASET_DESC
        else:
            self.datasetMetadata = deepcopy(datasetMetadata)

        """ Validate and store image """
        # Remove singleton dimensions
        self.image = nib.funcs.squeeze_image(image)

        # Validate dimensions, upgrading to 4-D if needed
        imageShape = self.imageDimensions
        if len(imageShape) < 3:
            raise ValueError("Image must have at least 3 dimensions")
        elif len(imageShape) == 3:
            # Add one singleton dimension to make image 4-D
            newData = np.expand_dims(getNiftiData(self.image), -1)
            self.image = self.image.__class__(newData, self.image.affine,
                                              self.image.header)
            # TODO(spolcyn): Fix xyzt units when data is extended from 3D to 4D
            logger.debug("Image header xyzt units: %s",
                         self.imageHeader['xyzt_units'])
            # Ensure time dimension size matches TR length
            self.imageHeader["pixdim"][4] = \
                self.getMetadataField("RepetitionTime")

        assert len(self.imageDimensions) == 4

        # Configure additional required BIDS metadata and files
        self.readme = "Generated BIDS-Incremental Dataset from RT-Cloud"

        eventDefaultHeaders = ['onset', 'duration', 'response_time']
        self.events = pd.DataFrame(columns=eventDefaultHeaders)

        # The BIDS-I version for serialization
        self.version = 1

    def __str__(self):
        return ("Image shape: {}; Metadata Key Count: {}; BIDS-I Version: {}"
                .format(self.imageDimensions,
                        len(self._imgMetadata.keys()),
                        self.version))

    def __eq__(self, other):
        def reportDifference(valueName: str, d1: dict, d2: dict,
                             equal: Callable[[Any, Any], bool] = opeq) -> None:
            logger.debug(valueName + " didn't match")
            difference = symmetricDictDifference(d1, d2, equal)
            logger.debug(valueName + " difference: %s", difference)

        # Compare images
        if self.image.header != other.image.header:
            reportDifference("Image headers",
                             dict(self.image.header),
                             dict(other.image.header),
                             np.array_equal)
            return False

        # Compare image metadata
        if self._imgMetadata != other._imgMetadata:
            reportDifference("Image metadata",
                             self._imgMetadata,
                             other._imgMetadata,
                             np.array_equal)
            return False

        # Compare dataset metadata
        if self.datasetMetadata != other.datasetMetadata:
            reportDifference("Dataset metadata",
                             self.datasetMetadata,
                             other.datasetMetadata)
            return False

        if not np.array_equal(self.imageData(), other.imageData()):
            differences = self.imageData() != other.imageData()
            logger.debug("Image data didn't match")
            logger.debug("Difference count: %d (%f%%)",
                         np.sum(differences),
                         np.sum(differences) / np.size(differences) * 100.0)
            return False

        return True

    def _preprocessAndSetMetadata(self, imageMetadata: dict) -> None:
        """
        Pre-process metadata to extract any additonal metadata that might be
        embedded in the provided metadata, like ProtocolName.
        """
        # Process ProtocolName
        protocolName = imageMetadata.get("ProtocolName", None)
        self._imgMetadata = metadataFromProtocolName(protocolName)
        logger.debug(f"From ProtocolName '{protocolName}', got: "
                     f"{self._imgMetadata}")

        # TODO(spolcyn): Attempt to extract the repetition time directly from
        # the NIfTI header when possible

        # TODO(spolcyn): Correctly extract slice timing from the metadata
        self._imgMetadata["SliceTiming"] = list(np.linspace(0.0, 1.5, 27))

        # TODO(spolcyn): Support volume timing and associated fields

        self._imgMetadata.update(imageMetadata)
        adjustTimeUnits(self._imgMetadata)

    def _postprocessMetadata(self) -> None:
        """
        Post-process metadata once all required fields are given to create
        derived fields (e.g., TaskName from task) and set data types to expected
        types (e.g., set run to an integer).
        """
        # Run should be an integer
        if self._imgMetadata.get("run", None) is not None:
            self._imgMetadata["run"] = int(self._imgMetadata["run"])

        # TaskName is required BIDS metadata that can be derived from the
        # required field, 'task'
        self._imgMetadata["TaskName"] = self._imgMetadata["task"]

    def _assertHaveRequiredMetadata(self) -> None:
        """
        Ensure that all required metadata is present, raising an exception with
        information on what's missing if not all is present.
        """
        missingImageMetadata = self.missingImageMetadata(self._imgMetadata)
        if missingImageMetadata != []:
            raise MissingMetadataError(f"Image metadata missing required "
                                       f"fields: {missingImageMetadata}")

    @staticmethod
    def createImageMetadataDict(subject: str, task: str, suffix: str,
                                datatype: str, repetitionTime: int,
                                echoTime: int):
        """
        Creates an image metadata dictionary for a BIDS-I with all of the
        basic required fields using the correct key names.

        Args:
            subject: Subject ID (e.g., '01')
            task: Task ID (e.g., 'story')
            suffix: Imaging method (e.g., 'bold')
            datatype: Data type (e.g., 'func' or 'anat')
            repetitionTime: TR time, in seconds, used for the imaging run
            echoTime: Echo time, in seconds, used for the imaging run

        Returns:
            Dictionary with the provided information ready for use in a BIDS-I

        """
        return {"subject": subject, "task": task, "suffix": suffix,
                'datatype': datatype, "RepetitionTime": repetitionTime,
                "EchoTime": echoTime}

    @classmethod
    def missingImageMetadata(cls, imageMeta: dict) -> list:
        return [f for f in cls.REQUIRED_IMAGE_METADATA if f not in imageMeta]

    @classmethod
    def isCompleteImageMetadata(cls, imageMeta: dict) -> bool:
        """
        Verifies that all required metadata fields for BIDS-I construction are
        present in the dictionary.

        Args:
            imageMeta: The dictionary with the metadata fields

        Returns:
            True if all required fields are present in the dictionary, False
            otherwise.

        """
        return len(cls.missingImageMetadata(imageMeta)) == 0

    def _exceptIfNotBids(self, entityName: str):
        """ Raise an exception if the argument is not a valid BIDS entity """
        if self.ENTITIES.get(entityName) is None:
            raise ValueError(f"{entityName} is not a valid BIDS entity name")

    # TODO(spolcyn): Add specific getters for commonly used things, like getRun,
    # getSubject, getTask
    def getMetadataField(self, field: str, strict: bool = False) -> str:
        """
        Get value for the field in the incremental's metadata, if it exists.

        Args:
            field: Metadata field to retrieve a value for.
            strict: Only allow getting official BIDS entity fields.

        Returns:
            Entity's value, or None if the entity isn't present in the metadata.

        Raises:
            ValueError if 'strict' is True and 'field' is not a BIDS entity.

        Examples:
            >>> incremental.getMetadataField('run')
            1
            >>> incremental.getMetadataField('task')
            'faces'
            >>> incremental.getMetadataField('RepetitionTime')
            1.5
            >>> incremental.getMetadataField('RepetitionTime', strict=True)
            ValueError: RepetitionTime is not a valid BIDS entity name
        """
        if strict:
            self._exceptIfNotBids(field)
        return self._imgMetadata.get(field, None)

    def setMetadataField(self, field: str, value, strict: bool = False) -> None:
        """
        Set metadata field to provided value.

        Args:
            field: Metadata field to set value for.
            value: Value to set for the provided entity.
            strict: Only allow setting of official BIDS entity fields.

        Raises:
            ValueError if 'strict' is True and 'field' is not a BIDS entity.
        """
        if strict:
            self._exceptIfNotBids(field)
        if field:
            self._imgMetadata[field] = value
        else:
            raise ValueError("Metadata field to set cannot be None")

    def removeMetadataField(self, field: str, strict: bool = False) -> None:
        """
        Remove a piece of metadata.

        Args:
            field: BIDS entity name to retrieve a value for.
            strict: Only allow remove of official BIDS entity fields.

        Raises:
            ValueError if 'strict' is True and 'field' is not a BIDS entity.
        """
        if field in self.REQUIRED_IMAGE_METADATA:
            raise ValueError(f"\"{field}\" is required and cannot be removed")

        if strict:
            self._exceptIfNotBids(field)
        self._imgMetadata.pop(field, None)

    @property
    def suffix(self) -> str:
        return self._imgMetadata.get("suffix")

    # Additional methods to access internal BIDS-I data
    @property
    def datatype(self) -> str:
        """ func or anat """
        return self._imgMetadata.get("datatype")

    @property
    def imageMetadata(self):
        return self._imgMetadata.copy()

    @property
    def entities(self) -> dict:
        """ Return new dictionary with the BIDS entities associated with this
        BIDS incremental """
        return filterEntities(self._imgMetadata)

    # Getting internal NIfTI data
    def imageData(self) -> np.ndarray:
        return getNiftiData(self.image)

    @property
    def imageHeader(self):
        return self.image.header

    @property
    def imageDimensions(self) -> tuple:
        return self.imageHeader.get_data_shape()

    """
    BEGIN BIDS-I ARCHIVE EMULTATION API

    A BIDS-I is meant to emulate a valid BIDS archive. Thus, an API is included
    that enables generating paths and filenames that would corresopnd to this
    BIDS-I's data if it were actually in an on-disk archive.

    """
    def makeBidsFileName(self, extension: BidsFileExtension) -> str:
        """
        Create the a BIDS-compatible file name based on the metadata. General
        format of the filename, per BIDS standard 1.4.1, is as follows (items in
        [square brackets] are considered optional):

        sub-<label>[_ses-<label>]_task-<label>[_acq-<label>] [_ce-<label>]
        [_dir-<label>][_rec-<label>][_run-<index>]
        [_echo-<index>]_<contrast_label >.ext

        Args:
            extension: The extension for the file, e.g., 'nii' for images or
                'json' for metadata

        Return:
            Filename from metadata according to BIDS standard 1.4.1.
        """
        entities = {key: self._imgMetadata[key] for key in self.ENTITIES.keys()
                    if self._imgMetadata.get(key, None) is not None}

        entities["extension"] = extension.value
        if extension == BidsFileExtension.EVENTS:
            entities["suffix"] = "events"
        else:
            entities["suffix"] = self._imgMetadata["suffix"]

        return bids_build_path(entities, BIDS_FILE_PATTERN)

    @property
    def datasetName(self) -> str:
        return self.datasetMetadata["Name"]

    @property
    def imageFileName(self) -> str:
        return self.makeBidsFileName(BidsFileExtension.IMAGE)

    @property
    def metadataFileName(self) -> str:
        return self.makeBidsFileName(BidsFileExtension.METADATA)

    @property
    def eventsFileName(self) -> str:
        return self.makeBidsFileName(BidsFileExtension.EVENTS)

    @property
    def imageFilePath(self) -> str:
        return os.path.join(self.dataDirPath, self.imageFileName)

    @property
    def metadataFilePath(self) -> str:
        return os.path.join(self.dataDirPath, self.metadataFileName)

    @property
    def dataDirPath(self) -> str:
        """
        Path to where this incremental's data would be in a BIDS archive,
        relative to the archive root.

        Returns:
            Path string relative to root of the imaginary dataset.

        Examples:
            >>> print(bidsi.dataDirPath)
            sub-01/ses-2011/anat

        """
        return bids_build_path(self._imgMetadata, BIDS_DIR_PATH_PATTERN)

    def writeToArchive(self, datasetRoot: str):
        """
        Writes the incremental's data to a directory on disk. NOTE: The
        directory is assumed to be empty, and no checks are made for data that
        would be overwritten.

        Args:
            datasetRoot: Path to the root of the BIDS archive to be written to.
        """
        dataDirPath = os.path.join(datasetRoot, self.dataDirPath)
        imagePath = os.path.join(dataDirPath, self.imageFileName)
        metadataPath = os.path.join(dataDirPath, self.metadataFileName)

        os.makedirs(dataDirPath, exist_ok=True)
        nib.save(self.image, imagePath)

        # Write out image metadata
        with open(metadataPath, mode='w') as metadataFile:
            # TODO(spolcyn): Don't write out entities like 'subject', "task",
            # and "run", as they're included in the filename
            metadataToWrite = {key: self._imgMetadata[key] for key in
                               self._imgMetadata if key not in self.ENTITIES}
            json.dump(metadataToWrite, metadataFile, sort_keys=True, indent=4)

        # TODO(spolcyn): Make events file correspond correctly to the imaging
        # sequence, not just to fulfill BIDS validation
        eventsPath = os.path.join(dataDirPath, self.eventsFileName)
        with open(eventsPath, mode='w') as eventsFile:
            self.events.to_csv(eventsFile, sep='\t')

        # Write out dataset description
        descriptionPath = os.path.join(datasetRoot, "dataset_description.json")
        with open(descriptionPath, mode='w') as description:
            json.dump(self.datasetMetadata, description, indent=4)

        # Write out readme
        with open(os.path.join(datasetRoot, "README"), mode='w') as readme:
            readme.write(self.readme)

    """ END BIDS-I ARCHIVE EMULTATION API """
