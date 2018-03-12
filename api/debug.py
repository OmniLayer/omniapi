import os, sys, commands

from config import DEBUG_LEVEL
LOGDIR=os.environ.get('LOGDIR')

def print_debug( msg, verbose):
  if int(verbose) < DEBUG_LEVEL:
    if type(msg) == tuple:
      temp=""
      for x in msg:
        temp+=str(x)+" "
      msg=temp
    print str(msg)
    #log_file(msg)

def log_file( msg ):
  commands.getoutput('echo '+msg+' >> '+LOGDIR+'/debug.log')

