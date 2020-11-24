import os, sys, commands
import datetime

from config import DEBUG_LEVEL
LOGDIR=os.environ.get('LOGDIR')

def print_debug( msg, verbose):
  if int(verbose) < DEBUG_LEVEL:
    if type(msg) == tuple:
      temp=""
      for x in msg:
        temp+=str(x)+" "
      msg=temp
    omsg=str(datetime.datetime.now())+": "+str(msg)
    print omsg
    sys.stdout.flush()
    #log_file(omsg)

def log_file( msg ):
  commands.getoutput('echo '+msg+' >> '+LOGDIR+'/debug.log')

