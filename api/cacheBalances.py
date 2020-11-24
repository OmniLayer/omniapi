from balancehelper import *
from cacher import *
import json, time, datetime

def printmsg(msg):
    print str(datetime.datetime.now())+str(" ")+str(msg)
    sys.stdout.flush()

def updateBalancesCache():
  while True:
    printmsg("Checking for balance updates")
    try:
      for space in rKeys("omniwallet:balances:addresses*"):
        addresses=rGet(space)
        if addresses != None:
          addresses = json.loads(addresses)
          printmsg("loaded "+str(len(addresses))+" addresses from redis "+str(space))
          balances=get_bulkbalancedata(addresses)
          rSet("omniwallet:balances:balbook"+str(space[29:]),json.dumps(balances))
          #expire balance data after 10 minutes (prevent stale data in case we crash)
          rExpire("omniwallet:balances:balbook"+str(space[29:]),600)
    except Exception as e:
      printmsg("error updating balances: "+str(space)+' '+str(e))
      #abort any previous txs and close connection so it can be reopened
      dbRollback()
    #dbCommit()
    time.sleep(30)


def main():
  updateBalancesCache()


if __name__ == "__main__":main() ## with if

