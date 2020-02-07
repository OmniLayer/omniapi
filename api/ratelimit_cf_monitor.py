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

def checkipstatus(cip):
  pList = redis.keys(pSpace+"*")
  bList = redis.keys(bSpace+"*")
  tList = redis.keys(tSpace+"*")
  lists={'p': pList, 'b': bList, 't': tList}
  retval={}
  for list in lists:
    for entry in lists[list]:
      try:
        ip = entry.split('/')[2]
        if ip==cip:
          retval[list]=entry
      except:
        pass
  return retval

def updateCFFirewall():
  printmsg("Checking for new entries")
  for entry in redis.keys(pSpace+"*"):
    try:
      ip=entry.split('/')[2]
      #check if address is already blocked
      if len( redis.keys(bSpace+str(ip)+"*") ) == 0:
        response=cffblock(ip)
        try:
          if response['success']:
            printmsg("Blocked Address "+str(ip))
            #repeat offenders get longer bans
            mfactor = int(redis.incr(tSpace+str(ip)))
            #expire 12 * mfactor hours from now
            eTime=int(time.time()) + int(43200 * mfactor)
            redis.set(bSpace+str(ip)+"/"+str(eTime),response['id'])
            redis.delete(entry)
          else:
            printmsg("error blocking ip "+str(ip)+" response "+str(response))
        except Exception as e:
          printmsg("error blocking ip "+str(ip)+" response "+str(response)+" error "+str(e))
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
        response = cffunblock(id)
        try:
          if response['success']:
            printmsg("Removing expired block ID:"+str(id)+" on "+str(ip))
            redis.delete(entry)
          else:
            printmsg("ERROR: Could not expire block "+str(id)+" on "+str(ip)+" response "+str(response))
        except Exception as e:
          printmsg("ERROR: Could not expire block "+str(id)+" on "+str(ip)+" response "+str(response)+" error "+str(e))
    except Exception as e:
      printmsg("error checking expired entries: "+str(e))

def backfillFromCFF():
  x=cffgetAll()
  for y in x['result']:
    if y['mode']=='block':
      id = y['id']
      if y['configuration']['target'] in ['ip','ip6']:
        ip = y['configuration']['value']
        if len( redis.keys(bSpace+str(ip)+"*") ) == 0:
          mfactor = int(redis.incr(tSpace+str(ip)))
          eTime=int(time.time()) + int(43200 * mfactor)
          redis.set(bSpace+str(ip)+"/"+str(eTime),id)

def importFromFile(fn):
  f = open(fn,"r")
  fl = f.readlines()
  for x in fl:
    sd = x.split("|")
    key = sd[0]
    value = sd[1]
    redis.set(key,value)

def main():
  while True:
    try:
      updateCFFirewall()
      checkExpiring()
      time.sleep(30)
    except Exception as e:
      printmsg("error running main loop: "+str(e))


if __name__ == "__main__":main() ## with if

