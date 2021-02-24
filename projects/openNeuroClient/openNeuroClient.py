# import important modules
import os
import sys
import argparse
import time
import toml

currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.dirname(os.path.dirname(currPath))
sys.path.append(rootPath)
from rtCommon.bidsArchive import BidsArchive
# import project modules from rt-cloud
from rtCommon.utils import loadConfigFile, stringPartialFormat
from rtCommon.clientInterface import ClientInterface
#from rtCommon.bidsInterface import BidsInterface
from rtCommon.OpenNeuroDownload import OpenNeuroOverview

# path for default configuration toml file
defaultConfig = os.path.join(currPath, 'conf/openNeuroClient.toml')


def doRuns(cfg, bidsInterface, subjInterface, webInterface):
    #openNeuro Example
    overview = OpenNeuroOverview()  # initialize OpenNeuroOverview
    print(overview.display_description("ds000102"))  # check description before download
    print(overview.display_readme("ds000102"))  # check readme file (if exists) before download
    # download a subject's data only and reformat it as BIDS-I
    dataset = overview.get_dataset("ds000102", False, "05")  # get dataset based on accession number and id
    loaded_cfg = toml.load(dataset[1])
    required_metadata = {k: loaded_cfg[k] for k in ('subject', 'task', 'suffix','run','datatype')}
    required_metadata['task'] = 'flanker'
    print(required_metadata)
    streamId = bidsInterface.init_bids_stream('ds000102_sub05', required_metadata,
                                              'archive')
    print(streamId)
    start = time.time()
    for i in range(100):
        next_img = bidsInterface.get_next_img(streamId)
        print(next_img)
        #time.sleep(.1)
    end = time.time()
    print(end-start)
    """
    # local dataset example
    required_metadata = cfg
    streamId = bidsInterface.init_bids_stream('ds000102', required_metadata, 'archive')
    print(streamId)
    start = time.time()
    for i in range(100):
        next_img = bidsInterface.get_next_img(streamId)
        print(next_img)
        #time.sleep(.1)
    end = time.time()
    print(end - start)
    """
def main(argv=None):
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--config', '-c', default=defaultConfig, type=str,
                           help='experiment config file (.json or .toml)')
    argParser.add_argument('--runs', '-r', default='', type=str,
                           help='Comma separated list of run numbers')
    argParser.add_argument('--scans', '-s', default='', type=str,
                           help='Comma separated list of scan number')
    args = argParser.parse_args(argv)


    # Initialize the RPC connection to the projectInterface
    # This will give us a dataInterface for retrieving files and
    # a subjectInterface for giving feedback
    clientInterfaces = ClientInterface()
    bidsInterface = clientInterfaces.bidsInterface
    subjInterface = clientInterfaces.subjInterface
    webInterface  = clientInterfaces.webInterface
    res = bidsInterface.echo("test")
    print(res)

    # load the experiment configuration file
    #TODO: check why loadConfigFile not works
    # cfg = loadConfigFile(args.config)
    cfg = toml.load(args.config)
    doRuns(cfg, bidsInterface, subjInterface, webInterface)

    return


if __name__ == "__main__":
    main()
    sys.exit(0)
