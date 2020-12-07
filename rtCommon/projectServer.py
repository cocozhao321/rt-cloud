import os
import sys
import time
import argparse
import threading
import logging
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.dirname(currPath)
sys.path.append(rootPath)
from rtCommon.structDict import StructDict
from rtCommon.utils import installLoggers
from rtCommon.errors import InvocationError
from rtCommon.webServer import Web, handleDataRequest, handleSubjectRequest
from rtCommon.projectServerRPC import startRPCThread, ProjectRPCService


class ProjectServer:
    """The main server for running a project. This server starts both the web server and an RPC server."""
    def __init__(self, args):
        if args is None:
            args = argparse.Namespace()
        if not hasattr(args, 'test'):
            args.test = False
        if not hasattr(args, 'dataremote'):
            args.dataremote = False
        if not hasattr(args, 'port'):
            args.port = 8888
        self.args = args
        self.params = StructDict(
            {'mainScript': args.mainScript,
             'initScript': args.initScript,
             'finalizeScript': args.finalizeScript,
             'port' : args.port,
            })

    def start(self):
        """Start the Web and RPC servers. This function doesn't return."""
        web = Web()
        # web.start(self.params, self.args.config, testMode=self.args.test)
        webThread = threading.Thread(name='webServerThread',
                                    target=web.start,
                                    args=(self.params, self.args.config,),
                                    kwargs={'testMode': self.args.test})
        webThread.setDaemon(True)
        webThread.start()
        # wait for the web to initialize
        while Web.ioLoopInst is None:
            time.sleep(0.5)

        rpcService = ProjectRPCService(dataremote=self.args.dataremote)
        rpcService.registerDataCommFunction(handleDataRequest)
        rpcService.registerSubjectCommFunction(handleSubjectRequest)
        rpcService.registerIoLoop(Web.ioLoopInst)
        startRPCThread(rpcService, hostname='localhost', port=12345)
        # rpcThread = threading.Thread(name='rpcThread',
        #                             target=startProjectRPCThread,
        #                             args=(rpcService,),
        #                             kwargs={'hostname': 'localhost',
        #                                     'port': 12345})
        # rpcThread.setDaemon(True)
        # rpcThread.start()




if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--projectName', '-p', default=None, type=str,
                           help='project name')
    argParser.add_argument('--projectDir', '-d', default=None, type=str,
                           help='project directory')
    argParser.add_argument('--config', '-c', default=None, type=str,
                           help='experiment file (.json or .toml)')
    argParser.add_argument('--mainScript', '-m', default=None, type=str,
                           help='project main script')
    argParser.add_argument('--initScript', '-i', default=None, type=str,
                           help='project initialization script')
    argParser.add_argument('--finalizeScript', '-f', default=None, type=str,
                           help='project finalization script')
    argParser.add_argument('--dataremote', '-x', default=False, action='store_true',
                           help='dicom files retrieved from remote server')
    argParser.add_argument('--test', '-t', default=False, action='store_true',
                           help='start webServer in test mode, unsecure')
    args = argParser.parse_args()

    if args.projectName is None:
        raise InvocationError('Must specify project name using -p parameter')
    if args.projectDir is None:
        args.projectDir = os.path.join(rootPath, 'projects', args.projectName)
    if args.config is None:
        args.config = os.path.join(args.projectDir, f'conf/{args.projectName}.toml')
    if args.mainScript is None:
        args.mainScript = os.path.join(args.projectDir, f'{args.projectName}.py')
    if args.initScript is None:
        args.initScript = os.path.join(args.projectDir, 'initialize.py')
    if args.finalizeScript is None:
        args.finalizeScript = os.path.join(args.projectDir, 'finalize.py')

    installLoggers(logging.INFO, logging.INFO, filename=os.path.join(currPath, f'logs/{args.projectName}.log'))

    # start the webServer server

    projectServer = ProjectServer(args)
    projectServer.start()
