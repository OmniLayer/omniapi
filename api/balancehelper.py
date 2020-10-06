import json
from sqltools import *
from blockchain_utils import *
from property_service import getpropertyraw
from cacher import *
from common import *
from validator import isvalid
from config import TESTNET

def get_balancedata(address):
    addr = re.sub(r'\W+', '', address) #check alphanumeric
    ret = {'bal': 0, 'pendingpos': 0, 'pendingneg': 0, 'error': 'invalid address'}
    try:
      if isvalid(addr):
        btcdata = bc_getbalance(addr)
        return getBalanceData(address,btcdata)
    except Exception as e:
      ret = {'bal': 0, 'pendingpos': 0, 'pendingneg': 0, 'error':str(address)+" "+str(e.message)}
    return ret

def get_bulkbalancedata(addresses):
    retval = {}
    for address in addresses:
      try:
        btcdata=bc_getbalance(address)
        balance_data=getBalanceData(address,btcdata)
        retval[address]=balance_data
      except Exception as e:
        print_debug(('get_bulkbalancedata error for address',address,e),4)
    return retval


def getBalanceData(address,btcdata):
    addr = re.sub(r'\W+', '', address) #check alphanumeric
    rev=raw_revision()
    cblock=rev['last_block']
    ckey="data:baldata:"+str(addr)+":"+str(cblock)

    #load btc data
    btcbal = btcdata['bal']
    btcpp = btcdata['pendingpos']
    btcpn = btcdata['pendingneg']
    btc_bal_err_msg = btcdata['error']
    if btc_bal_err_msg != None or btcbal == '':
      btc_bal = str(0)
      btc_pp = str(0)
      btc_pn = str(0)
      btc_bal_err = True
    else:
      try:
        btc_bal = str(btcbal)
        btc_pp = str(btcpp)
        btc_pn = str(btcpn)
        btc_bal_err = False
      except ValueError:
        btc_bal = str(0)
        btc_pp = str(0)
        btc_pn = str(0)
        btc_bal_err = True

    try:
      #check cache
      balance_data = json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
      for brow in balance_data['balance']:
        if brow['id']==0:
          brow['value']=btc_bal
          brow['pendingpos']=btc_pp
          brow['pendingneg']=btc_pn
          brow['error']=btc_bal_err
          brow['errormsg']=btc_bal_err_msg
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect("""select
                       f1.propertyid, sp.propertytype, f1.balanceavailable, f1.pendingpos, f1.pendingneg, f1.balancereserved, f1.balancefrozen
                     from
                       (select
                          COALESCE(s1.propertyid,s2.propertyid) as propertyid, COALESCE(s1.balanceavailable,0) as balanceavailable, COALESCE(s1.balancefrozen,0) as balancefrozen,
                          COALESCE(s2.pendingpos,0) as pendingpos,COALESCE(s2.pendingneg,0) as pendingneg, COALESCE(s1.balancereserved,0) as balancereserved
                        from
                          (select propertyid,balanceavailable,balancereserved,balancefrozen
                           from addressbalances
                           where address=%s) s1
                        full join
                          (SELECT atx.propertyid,
                             sum(CASE WHEN atx.balanceavailablecreditdebit > 0 THEN atx.balanceavailablecreditdebit ELSE 0 END) AS pendingpos,
                             sum(CASE WHEN atx.balanceavailablecreditdebit < 0 THEN atx.balanceavailablecreditdebit ELSE 0 END) AS pendingneg
                           from
                             addressesintxs atx, transactions tx
                           where
                             atx.txdbserialnum=tx.txdbserialnum
                             and tx.txstate='pending'
                             and tx.txdbserialnum<-1
                             and atx.address=%s
                           group by
                             atx.propertyid) s2
                        on s1.propertyid=s2.propertyid) f1
                     inner join smartproperties sp
                     on f1.propertyid=sp.propertyid and (sp.protocol='Omni' or sp.protocol='Bitcoin')
                     order by f1.propertyid""",(addr,addr))
      balance_data = { 'balance': [] }
      for balrow in ROWS:
        cID = str(int(balrow[0])) #currency id
        sym_t = ('BTC' if cID == '0' else ('OMNI' if cID == '1' else ('T-OMNI' if cID == '2' else 'SP' + cID) ) ) #symbol template
        #1 = new indivisible property, 2=new divisible property (per spec)
        divi = True if int(balrow[1]) == 2 else False
        res = { 'symbol' : sym_t, 'divisible' : divi, 'id' : cID }
        #inject property details but remove issuanecs
        res['propertyinfo'] = getpropertyraw(cID)
        if 'issuances' in res['propertyinfo']:
          res['propertyinfo'].pop('issuances')
        res['pendingpos'] = str(long(balrow[3]))
        res['pendingneg'] = str(long(balrow[4]))
        res['reserved'] = str(long(balrow[5]))
        res['frozen'] = str(long(balrow[6]))
        if cID == '0':
          res['value']=btc_bal
          res['pendingpos']=btc_pp
          res['pendingneg']=btc_pn
          res['error']=btc_bal_err
          res['errormsg']=btc_bal_err_msg
        else:
          #get regular balance from db 
          #if balrow[4] < 0 and not balrow[6] > 0:
          #  #update the 'available' balance immediately when the sender sent something. prevent double spend as long as its not frozen
          #  res['value'] = str(long(balrow[2]+balrow[4]))
          #else:
          res['value'] = str(long(balrow[2]))
        balance_data['balance'].append(res)
      #check if we got BTC data from DB, if not trigger manually add
      addbtc=True
      for x in balance_data['balance']:
        if x['id'] == 0:
          addbtc=False
      if addbtc:
        btc_balance = { 'symbol': 'BTC',
                        'divisible': True,
                        'id' : '0',
                        'value' : btc_bal,
                        'pendingpos' : btc_pp,
                        'pendingneg' : btc_pn,
                        'propertyinfo' : getpropertyraw(0),
                        'error' : btc_bal_err,
                        'errormsg' : btc_bal_err_msg
                      }
        balance_data['balance'].append(btc_balance)
      #cache result for 1 min
      lSet(ckey,json.dumps(balance_data))
      lExpire(ckey,60)
    return balance_data
