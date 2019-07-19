from cloudflare import *
from cacher import *
import json, time, datetime

#init ratelimit redis key store on db 1
redis = lInit(1)
#pending nameSpace
pSpace = "global/pending/"
#blocked nameSpace
bSpace = "global/blocked/"
#tracking nameSpace
tSpace = "global/offenders/"

def printmsg(msg):
    print str(datetime.datetime.now())+str(" ")+str(msg)
    sys.stdout.flush()

def updateCFFirewall():
  printmsg("Checking for new entries")
  for entry in redis.keys(pSpace+"*"):
    try:
      ip=entry.split('/')[2]
      #check if address is already blocked
      if len( redis.keys(bSpace+str(ip)+"*") ) == 0:
        ret=cffblock(ip)
        if ret['success']:
          printmsg("Blocked Address "+str(ip))
          redis.delete(entry)
          #repeat offenders get longer bans
          mfactor = int(redis.incr(tSpace+str(ip)))
          #expire 12 * mfactor hours from now
          eTime=int(time.time()) + int(43200 * mfactor)
          redis.set(bSpace+str(ip)+"/"+str(eTime),ret['id'])
      else:
        redis.delete(entry)
    except Exception as e:
      printmsg("error blocking abuse entries: "+str(e))

def checkExpiring():
  list = redis.keys(bSpace+"*")
  printmsg("Checking "+str(len(list))+" records for expired entries")
  for entry in list:
    try:
      ip = entry.split('/')[2]
      eTime = int(entry.split('/')[3])
      now = int(time.time())
      if eTime < now:
        id = redis.get(entry)
        if cffunblock(id):
          printmsg("Removing expired block ID:"+str(id)+" on "+str(ip))
          redis.delete(entry)
        else:
          printmsg("ERROR: Could not expire block "+str(id)+" on "+str(ip))
    except Exception as e:
      printmsg("error checking expired entries: "+str(e))


def main():
  while True:
    try:
      updateCFFirewall()
      checkExpiring()
      time.sleep(30)
    except Exception as e:
      printmsg("error running main loop: "+str(e))


if __name__ == "__main__":main() ## with if

