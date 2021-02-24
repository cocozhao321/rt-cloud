# openNeuroClient Example Instruction
**Note:** 
1. The --test option runs in test mode which doesn't use SSL encryption and accepts a default username and password, 
both are 'test'. **Never run with the --test option in production.**
2. The default setting for this example is downloading openNeuro dataset to your local computer and stream it as
an realtime experiment. 

####Changes you need made in python files
1. Open rtCommon/bidsStreamer.py
    - update defaultPath (line 14) to path where you will download bids dataset
2. Open rtCommon/OpenNeuroDownload.py
    - update defaultPath (line 11) to path where you will download bids dataset
3. (Optional) test existing dataset 
    - Open projects/openNeuroClient.py
    - Comment out openNeuro example section(line 22 - 42)
    - Uncomment local dataset example section(line 45 - 55)
####Testing the example 
1. Open a terminal
    - Start the projectInterface<br>
        - <code>conda activate rtcloud</code>
        - <code>bash scripts/run-projectInterface.sh -p sample --dataRemote --subjectRemote --test</code>
2. Open another terminal
    - Start the dataScannerService<br>
        - <code>conda activate rtcloud</code>
        - <code>bash scripts/run-scannerDataService.sh -s localhost:8888 -d $PWD,/tmp --test</code>
3. Open a third terminal to start the subjectService (where feedback is received)
    - Run the project from the command line (it will automatically connect to a local projectServer and receive data from the scannerDataService)<br>
    - <code>conda activate rtcloud</code>
    - <code>python projects/openNeuroClient/openNeuroClient.py</code>

