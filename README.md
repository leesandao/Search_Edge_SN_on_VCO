# Search_Edge_SN_on_VCO
If you want to verify Edge existed on VCO or not, you may use this script

# Use Guide
For Windows Environment, you can use directly with necessary import modules
C:\Users\raynorl\Sample_by_Raynor>python Search_all_Edges_SN.py

For Linux/MacOS Environment, you need to 
change filepath at line 33
path=os.getenv('VCO_COOKIE_PATH', "C:/Temp/")):
to
path=os.getenv('VCO_COOKIE_PATH', "/tmp/")):
or any path you like,

Then run the script
