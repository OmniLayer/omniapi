import urlparse
import os, sys, re
import math
#from flask import Flask, request, Response, jsonify, abort, json, make_response
from flask_rate_limit import *
from common import *
from decimal import Decimal
from blockchain_utils import *
from cacher import *
from properties_service import getpropnamelist
from debug import *
from validator import isvalid

app = Flask(__name__)
app.debug = True

@app.route('/estimatefee/<addr>', methods=['GET','POST'])
@ratelimit(limit=10, per=60)
def estimatefees(addr):
    try:
      address = str(re.sub(r'\W+', '', addr ) ) #check alphanumeric
    except ValueError:
      abort(make_response('This endpoint only consumes valid input', 400))

    try:
      amountBTC=int( Decimal(request.form['amountBTC']) * Decimal(1e8))
    except:
      amountBTC=0

    #get dynamic fee rates from db
    try:
      fees=getfeesRaw()
    except Exception as e:
      print_debug(("Fee lookup failed, falling back",e),2)
      fees={"unit": "Satoshi/kB", "faster": 275000, "fast": 245000, "normal": 215000}

    #initial miner fee estimate
    mfee=25000

    #class B tx: output base cost
    cbb=4410

    #Class C tx: output base cost
    ccb=546

    ins=1
    outs=2

    amount=ccb+mfee+amountBTC

    balance=bc_getbalance(address)
    if 'bal' in balance and balance['bal']>0:
      unspent=bc_getutxo(addr,amount)
      if 'utxos' in unspent:
        ins=len(unspent['utxos'])
        if unspent['avail'] == amount:
          outs=1

    #ins + outs + header + opreturn
    size=ins*180 + outs*34 + 10 + 80
    tsize=math.ceil((size+180)*1.05)

    faster = '%.8f' % ( Decimal(int((size * fees['faster'])/1000)) / Decimal(1e8) )
    fast = '%.8f' % ( Decimal(int((size * fees['fast'])/1000)) / Decimal(1e8) )
    normal = '%.8f' % ( Decimal(int((size * fees['normal'])/1000)) / Decimal(1e8) )

    tfaster = '%.8f' % ( Decimal(int((tsize * fees['faster'])/1000)) / Decimal(1e8) )
    tfast = '%.8f' % ( Decimal(int((tsize * fees['fast'])/1000)) / Decimal(1e8) )
    tnormal = '%.8f' % ( Decimal(int((tsize * fees['normal'])/1000)) / Decimal(1e8) )

    ret={"address":addr,
         "class_c":{"faster": faster, "fast": fast, "normal": normal, "estimates":{"size":size, "ins":ins, "outs":outs} },
         "topup_c":{"faster": tfaster, "fast": tfast, "normal": tnormal, "estimates":{"size":tsize, "ins":ins+1, "outs":outs} }
        }
    return jsonify(ret)

@app.route('/fees')
@ratelimit(limit=20, per=60)
def getfees():
    return jsonify(getfeesRaw())

def getfeesRaw():
    ckey="info:fees"
    fee={}
    try:
      #check cache first
      fee=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect("select value from settings where key='feeEstimates'")
      print_debug(ROWS,2)
      if len(ROWS) > 0:
        fee=json.loads(ROWS[0][0])
      #cache result for 10 min
      lSet(ckey,json.dumps(fee))
      lExpire(ckey,600)

    fee['unit']='Satoshi/kB'
    return fee

#not implimented yet
#@app.route('/estimatetxcost', methods=['POST'])
def estimatetxcost():
    try:
        address = str(re.sub(r'\W+', '', request.form['address'] ) ) #check alphanumeric
        type = int(re.sub(r'\d', '', request.form['txtype'] ) )
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))


@app.route('/address/<page>', methods=['POST'])
@ratelimit(limit=5, per=30)
def getaddresshistpage(page=0):
    try:
        address = str(re.sub(r'\W+', '', request.form['addr'] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))
    try:
      page=int(page)
    except:
      page=0
    return jsonify(getaddresshistraw(address,page))


@app.route('/address', methods=['POST'])
@ratelimit(limit=10, per=30)
def getaddresshist():
    try:
        address = str(re.sub(r'\W+', '', request.form['addr'] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    try:
      page=int(request.form['page'])
    except:
      page=0
    return jsonify(getaddresshistraw(address,page))


@app.route('/addresses', methods=['POST'])
@ratelimit(limit=5, per=30)
def getaddresseshist():
    try:
      addrs_list=request.form.getlist('addr')
    except KeyError:
      return jsonify({"error":"'addr' field not supplied"})

    if len(addrs_list)<1:
      return jsonify({"error":"This endpoint requires at least 1 address."})
    elif len(addrs_list)>10:
      return jsonify({"error":"This endpoint accepts at most 10 addresses."})

    clean_list={}
    for addr in addrs_list:
      data=addr.split(":")
      try:
        page=int(data[1])
      except:
        page=0
      a = re.sub(r'\W+', '', data[0]) #check alphanumeric
      if isvalid(a):
        clean_list[a]=getaddresshistraw(a,page)
    return jsonify(clean_list)


def getaddresshistraw(address,page):
    rev=raw_revision()
    cblock=rev['last_block']

    try:
      page=int(page)
    except:
      page=1

    atc=getaddresstxcount(address)
    pcount=atc['pages']
    txcount=atc['txcount']
    adjpage=page
    adjpage-=1
    if adjpage<0:
      adjpage=0
    if adjpage>pcount:
      adjpage=pcount

    #toadd=[]
    limit=10
    offset=adjpage*10
    ckey="data:addrhist:"+str(address)+":"+str(adjpage)
    try:
      #check cache
      txlist = json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)

      ROWS=[]
      if limit > 0:
        #ROWS=dbSelect("select txj.txdata from txjson txj, (select distinct txdbserialnum from addressesintxs where address=%s and txdbserialnum > 0) q where q.txdbserialnum=txj.txdbserialnum order by txj.txdbserialnum desc limit %s offset %s",(address,limit,offset))
        #ROWS=dbSelect("select txdata from txjson where (txdata->>'sendingaddress'=%s or txdata->>'referenceaddress'=%s) and txdbserialnum > 0 order by txdbserialnum desc limit %s offset %s",(address,address,limit,offset))
        ROWS=dbSelect("with temp as (select distinct(txdbserialnum) as txdbserialnum from addressesintxs where address=%s and txdbserialnum > 0 order by txdbserialnum desc limit %s offset %s) select txj.txdata from txjson txj, temp where txj.txdbserialnum=temp.txdbserialnum",(address,limit,offset))
      #set and cache data for 7 min
      pnl=getpropnamelist()
      txlist=[]
      for r in ROWS:
        txJson=addName(r[0],pnl)
        txlist.append(txJson)
      #txlist = toadd+txlist
      lSet(ckey,json.dumps(txlist))
      lExpire(ckey,420)

    for tx in txlist:
      try:
        tx['confirmations'] = cblock - tx['block'] + 1
      except:
        pass

    cachetxs(txlist)
    response = { 'address': address, 'transactions': txlist , 'pages': pcount, 'current_page': page , 'txcount': txcount }

    return response


def getaddress_OLD():
    try:
        address = str(re.sub(r'\W+', '', request.form['addr'] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    ROWS=dbSelect("""select t.TxHash, t.TxType, t.TxRecvTime, t.TxState,
                            atx.AddressRole, atx.BalanceAvailableCreditDebit,
                            sp.PropertyData
                      from transactions t, addressesintxs atx, smartproperties sp
                      where t.txdbserialnum = atx.txdbserialnum and sp.PropertyID = atx.PropertyID and atx.address=%s and t.txdbserialnum >0
                      and sp.Protocol != 'Fiat'
                      order by t.txdbserialnum DESC""", [address])

    transactions = []

    if len(ROWS) > 0:
      for txrow in ROWS:
        transaction = {}

        transaction['hash'] = txrow[0]
        transaction['type'] = txrow[1]
        transaction['time'] = txrow[2]
        transaction['state'] = txrow[3]
        transaction['role'] = txrow[4]
        transaction['amount'] = str(txrow[5])
        transaction['currency'] = txrow[6]

        transactions.append(transaction)

    response = { 'address': address, 'transactions': transactions }

    return jsonify(response)

def getpagecounttxjson(limit=10):
  ckey="info:tx:pcount"
  try:
    rc = lGet(ckey)
    if rc in ['None',None]:
      raise "not in cache"
    else:
      count=int(rc)
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select max(id) from txjson;")
    count=int(ROWS[0][0])
    #cache 10 min
    lSet(ckey,count)
    lExpire(ckey,600)

  ret=(count/limit)
  if (count % limit > 0):
    ret+=1

  return ret

def getaddresstxcount(address,limit=10):
  ckey="info:addr:"+str(address)+":pcount"
  try:
    rc = lGet(ckey)
    if rc in ['None',None]:
      raise "not in cache"
    else:
      count=int(rc)
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select txcount from addressstats where address=%s",[address])
    #PROWS=dbSelect("select count(*) from (select distinct txdbserialnum from addressesintxs where address=%s and txdbserialnum<0) as temp;",[address])
    try:
      lc=int(ROWS[0][0])
    except:
      lc=0
    #try:
    #  pc=int(PROWS[0][0])
    #except:
    #  pc=0
    #count=lc+pc
    count=lc
    lSet(ckey,count)
    lExpire(ckey,180)

  pages=(count/limit)
  if (count % limit > 0):
    pages+=1

  return {'pages':pages,'txcount':count}


@app.route('/recentab/')
@ratelimit(limit=10, per=10)
def getrecentclassab():
    rev=raw_revision()
    cblock=rev['last_block']
    ckey="data:tx:recentab:"+str(cblock)
    try:
      response=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)

      limit = 50
      ROWS=dbSelect("select txj.txdata from txjson txj,transactions tx where tx.txdbserialnum = txj.txdbserialnum and txj.protocol = 'Omni' and (tx.txclass = 1 or tx.txclass = 2) and txj.txdbserialnum > 0 order by txj.txdbserialnum DESC limit %s;",[limit])

      data = []
      pnl=getpropnamelist()
      if len(ROWS) > 0:
        for d in ROWS:
          res = addName(d[0],pnl)
          try:
            res['confirmations'] = cblock - res['block'] + 1
          except:
            pass
          #if cblock hasn't caught up make sure we don't return negative weirdness
          if res['confirmations'] < 0:
            res['confirmations'] = 0
          data.append(res)
      response={'note':'Endpoint returns 50 most recent txs only', 'transactions':data}
      #cache pages for 1 hour
      lSet(ckey,json.dumps(response))
      lExpire(ckey,3600)
      cachetxs(data)
    return jsonify(response)


#@app.route('/general/')
#@ratelimit(limit=10, per=10)
def getrecenttx():
  return getrecenttxpages()

#@app.route('/general/<page>', methods=['GET','POST'])
#@ratelimit(limit=10, per=10)
def getrecenttxpages(page=1):
    #pagination starts at 1 so adjust accordingly to treat page 0 and 1 the same
    try:
      page=int(page)
    except:
      page=1

    page-=1
    if page < 0:
      page=0

    if page>100:
      page=100

    try:
      offset=int(page)*10
    except:
      offset=0
      page=0

    filters = {
      0 : [0],
      3 : [3],
      20: [20,22,-21],
      25: [25,26,27,28],
      50: [50,51,54],
      55: [55],
      56: [56]
    }

    try:
      filter=int(request.form['tx_type'])
      tx_type=filters[filter]
    except:
      filter=9999
      tx_type=None

    rev=raw_revision()
    cblock=rev['last_block']
    toadd=[]
    limit=10

    #ckey="data:tx:general:"+str(cblock)+":"+str(filter)+":"+str(page)
    ckey="data:tx:general:"+str(cblock)+":"+str(page)
    try:
      response=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)

      raw=getrawpending()
      try:
        pending=raw['data']
        count=len(pending)

        if count > 0:
          max=offset+10
          if max > count:
            max = count

          for x in range(offset,max):
            toadd.append(pending[x])

          limit-=len(toadd)
          offset -= count
          if offset < 0:
            offset = 0
      except Exception as e:
        print_debug(("getgeneral pending inject failed",e),2)
        pass

      #if filter==9999:
      ROWS=dbSelect("select txdata from txjson txj where protocol = 'Omni' and txdbserialnum > 0 order by txdbserialnum DESC offset %s limit %s;",(offset,limit))
      #else:
      #  ROWS=dbSelect("select txdata from txjson where cast(txdata->>'type_int' as numeric) = ANY(%s) and "
      #                "protocol = 'Omni' and txdbserialnum > 0 order by txdbserialnum DESC offset %s limit %s;",(tx_type,offset,limit))

      data = []
      pnl=getpropnamelist()
      if len(ROWS) > 0:
        for d in ROWS:
          res = addName(d[0],pnl)
          try:
            res['confirmations'] = cblock - res['block'] + 1
          except:
            pass
          #if cblock hasn't caught up make sure we don't return negative weirdness
          if res['confirmations'] < 0:
            res['confirmations'] = 0
          data.append(res)
      pages=getpagecounttxjson()
      data=toadd+data
      response={'pages':pages,'transactions':data}
      #cache pages for 5 min
      lSet(ckey,json.dumps(response))
      lExpire(ckey,300)
      cachetxs(data)

    return jsonify(response)


def cachetxs(txlist):
    for tx in txlist:
      ckey="data:tx:"+str(tx['txid'])
      lSet(ckey,json.dumps(tx))
      try:
        #check if tx is unconfirmed and expire cache after 5 min if it is, otherwise 4 weeks
        if tx['confirmations'] == 0:
          lExpire(ckey,300)
	else:
	  lExpire(ckey,2419200)
      except:
        print_debug(("error expiring",ckey,tx),2)
        lExpire(ckey,300)


@app.route('/unconfirmed/<addr>')
@ratelimit(limit=10, per=10)
def getaddrpending(addr):
  try:
    addr_ = str(re.sub(r'\W+', '', addr.split('.')[0] ) ) #check alphanumeric
  except ValueError:
    abort(make_response('This endpoint only consumes valid input', 400))
  rawpend=getrawpending(addr_)
  try:
    ret=rawpend['index'][addr_]
  except:
    ret=[]
  return jsonify({'data':ret,'address':addr_})


@app.route('/unconfirmed')
@ratelimit(limit=20, per=60)
def getpending():
    ret=getrawpending()
    return jsonify({'data':ret['data']})


def getrawpending(addr=None):
    rev=raw_revision()
    cblock=rev['last_block']
    ckey="data:tx:pendinglist:"+str(cblock)
    if addr is not None:
      ckey = ckey+":"+str(addr)
    try:
      response=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      if addr is not None:
        ROWS=dbSelect("select txj.txdata, extract(epoch from tx.txrecvtime) from txjson txj,transactions tx,addressesintxs atx where tx.txdbserialnum=txj.txdbserialnum and atx.txdbserialnum=txj.txdbserialnum and atx.address=%s and txj.protocol = 'Omni' and txj.txdbserialnum < 0 order by txj.txdbserialnum ASC limit 25;",[addr])
      else:
        ROWS=dbSelect("select txj.txdata, extract(epoch from tx.txrecvtime) from txjson txj,transactions tx where tx.txdbserialnum=txj.txdbserialnum and txj.protocol = 'Omni' and txj.txdbserialnum < 0 order by txj.txdbserialnum ASC limit 25;")
      data = []
      index = {}
      pnl=getpropnamelist()
      if len(ROWS) > 0:
        for d in ROWS:
          res = addName(d[0],pnl)
          if 'blocktime' not in res:
            try:
              res['blocktime']=int(d[1])
            except:
              pass
          data.append(res)
          #index by sending address
          try:
            index[res['sendingaddress']].append(res)
          except:
            index[res['sendingaddress']]=[res]
          #index by receiving address if exists
          try:
            index[res['referenceaddress']].append(res)
          except:
            try:
              index[res['referenceaddress']]=[res]
            except:
              pass
      response={'data':data,'index':index}
      #cache for 1 min
      lSet(ckey,json.dumps(response))
      lExpire(ckey,60)
    return response

def gettxjson(hash_id):
    try:
        transaction_ = str(re.sub(r'\W+', '', hash_id.split('.')[0] ) ) #check alphanumeric
    except ValueError:
        return {'error':'This endpoint only consumes valid input. Invalid txid'}

    rev=raw_revision()
    cblock=rev['last_block']

    ckey="data:tx:"+str(transaction_)
    try:
      txJson=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)

      if len(transaction_) == 64:
        #ROWS=dbSelect("select txj.txdata, extract(epoch from t.txrecvtime) from transactions t, txjson txj where t.txdbserialnum = txj.txdbserialnum and t.protocol != 'Bitcoin' and t.txhash=%s", [transaction_])
        ROWS=dbSelect("select txdata,txdbserialnum from txjson where txdata->>'txid'=%s", [transaction_])
      else:
        ROWS=[]

      if len(ROWS) < 1:
        txJson={'txid':transaction_,'type':'Error - Not Found'}
      else:
        try:
          txj = json.loads(ROWS[0][0])
        except TypeError:
          txj = ROWS[0][0]
        try:
          if 'type_int' not in txj and txj['type']=="DEx Purchase":
            txj['type_int']=-22
        except:
          pass
        txJson=addName(txj,getpropnamelist())
        if 'blocktime' not in txJson:
          try:
            txdbserial=ROWS[0][1]
            blk_time=dbSelect("select extract(epoch from txrecvtime) from transactions where txdbserialnum = %s", [txdbserial])
            txJson['blocktime']=int(blk_time[0][0])
          except: 
            pass
      lSet(ckey,json.dumps(txJson))
      try:
        #check if tx is unconfirmed and expire cache after 5 min if it is otherwise 4 weeks
        if txJson['confirmations'] == 0:
          lExpire(ckey,300)
        else:
          lExpire(ckey,2419200)
      except:
        lExpire(ckey,100)

    try:
      if 'type_int' not in txJson and txJson['type']=="DEx Purchase":
        txJson['type_int']=-22
    except:
      pass
    try:
      txJson['confirmations'] = cblock - txJson['block'] + 1
    except:
      pass

    try:
      #if cblock hasn't caught up make sure we don't return negative weirdness
      if txJson['confirmations'] < 0:
        txJson['confirmations'] = 0
    except:
      pass

    return txJson

def getblockhash(blocknumber):
  try:
    block_ = int( blocknumber ) #check numeric
  except Exception as e:
    return {'error':'This endpoint only consumes valid input. Invalid block'}

  ckey="info:blockhash:"+str(block_)
  try:
    bhash=lGet(ckey)
    if bhash in ['None',None]:
      raise "not cached"
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select blockhash from blocks where blocknumber=%s", [block_])
    if len(ROWS) < 1:
      bhash="error: block not available."
    else:
      bhash=ROWS[0][0]
    #cache for 10 min
    lSet(ckey,bhash)
    lExpire(ckey,600)

  return bhash


@app.route('/blocks/')
@ratelimit(limit=10, per=10)
def getblockslisthelper():
  return getblockslist()


@app.route('/blocks/<lastblock>', methods=['GET','POST'])
@ratelimit(limit=10, per=10)
def getblockslist(lastblock=0):
  return jsonify(getblockslistraw(lastblock))

def getblockslistraw(lastblock=0):
  try:
    block=int(lastblock)
  except:
    block=0
  rev=raw_revision()
  cblock=rev['last_block']
  if block<1 or block>cblock:
    block=cblock
  ckey="data:tx:blocks:"+str(block)
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select t.blocknumber,extract(epoch from t.blocktime),t.blockcount,b.blockhash,t.value from txstats t, blocks b where t.blocknumber=b.blocknumber and t.blocknumber <= %s order by t.blocknumber desc limit 10;",[block])
    response={'latest':cblock, 'blocks':[]}
    pnl=getpropnamelist()
    for r in ROWS:
      bnum=r[0]
      try:
        value=r[4]
        q=value['total_usd']
      except:
        try:
          value=json.loads(r[4])
        except:
          value={'error':True, 'msg':'calculations missing'}
      try:
        for pid in value['details']:
          value['details'][pid]['name']=pnl[str(pid)]['name']
          value['details'][pid]['flags']=pnl[str(pid)]['flags']
      except:
        pass
      ret={'block':bnum, 'timestamp':r[1], 'omni_tx_count':r[2], 'block_hash':r[3], 'value':value}
      response['blocks'].append(ret)
    #cache block list for 6 hours
    lSet(ckey,json.dumps(response))
    lExpire(ckey,21600)
  response['latest']=cblock
  return response


@app.route('/block/<block>', methods=['GET','POST'])
@ratelimit(limit=10, per=10)
def getblocktx(block):
  rev=raw_revision()
  cblock=rev['last_block']
  try:
    _block=int(block)
    if _block<1 or _block>cblock:
      raise "invalid block"
    ret=getblocktxjson(_block)
  except:
    ret={"error": "This endpoint only consumes valid input. Invalid/Unknown blocknumber"}
  return jsonify(ret)

def getblocktxjson(block):
  bhash=getblockhash(block)
  if "error" in bhash:
    return bhash

  rev=raw_revision()
  cblock=rev['last_block']

  ckey="data:block:txjson:"+str(block)
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    try:
        block_ = int( block ) #check numeric
        ROWS=dbSelect("select txj.txdata from transactions t, txjson txj where t.txdbserialnum = txj.txdbserialnum and t.protocol != 'Bitcoin' and t.txblocknumber=%s", [block_])
    except Exception as e:
        return {'error':'This endpoint only consumes valid input. Invalid block'}

    pnl=getpropnamelist()
    ret=[]
    for x in ROWS:
      try:
        txJson = json.loads(x[0])
      except TypeError:
        txJson = x[0]
      ret.append(addName(txJson,pnl))

    response = {"block":block_, "blockhash":bhash, "transactions": ret, "count": len(ret)}
    #cache for 6 hours
    lSet(ckey,json.dumps(response))
    lExpire(ckey,21600)

  for res in response['transactions']:
    try:
      res['confirmations'] = cblock - res['block'] + 1
    except:
      pass
    #if cblock hasn't caught up make sure we don't return negative weirdness
    if res['confirmations'] < 0:
      res['confirmations'] = 0

  return response

def getaddrhist(address,direction='both',page=1):
    try:
      page=int(page)
    except:
      page=1

    page-=1
    if page<0:
      page=0

    try:
        address_ = str(re.sub(r'\W+', '', address.split('.')[0] ) ) #check alphanumeric
    except ValueError:
        return {'error':'This endpoint only consumes valid input. Invalid address'}

    try:
      offset=int(page)*50
    except:
      offset=0
      page=0

    query="select t.txhash from transactions t, addressesintxs atx where t.txdbserialnum = atx.txdbserialnum and t.protocol != 'Bitcoin' and atx.address='"+str(address_)+"'"
    role='address'
    if direction=='send':
      role='sender'
      query+=" and atx.addressrole='sender'"
    elif direction=='receive':
      role="recipient"
      query+=" and atx.addressrole='recipient'"
    query+=" order by t.txdbserialnum DESC offset " +str(offset)+ " limit 50"

    ckey="data:oe:addrhist:"+str(address_)+":"+str(direction)
    try:
      ret=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect(query)
      ret=[]
      for x in ROWS:
        ret.append(x[0])
      lSet(ckey,json.dumps(ret))
      lExpire(ckey,300)

    return {role:address_,"transactions":ret}

@app.route('/tx/<hash_id>')
@ratelimit(limit=20, per=60)
def gettransaction(hash_id):
    try:
        transaction_ = str(re.sub(r'\W+', '', hash_id.split('.')[0] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    return jsonify(gettxjson(transaction_))

def gettransaction_OLD(hash_id):
    try:
        transaction_ = str(re.sub(r'\W+', '', hash_id.split('.')[0] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    ROWS=dbSelect("select t.txhash,t.protocol,t.txdbserialnum,t.txtype,t.txversion,t.ecosystem,t.txrecvtime,t.txstate,t.txerrorcode,"
                  "t.txblocknumber,t.txseqinblock,txj.txdbserialnum,txj.protocol,txj.txdata "
                  "from transactions t, txjson txj where t.txdbserialnum = txj.txdbserialnum and t.protocol != 'Bitcoin' and t.txhash=%s", [transaction_])

    if len(ROWS) < 1:
      return json.dumps([])

    def dehexify(hex_str):
        temp_str=[]
        for let in hex_str:
            if ord(let) < 128:
                temp_str.append(let)
            else:
                temp_str.append('?')
        return ''.join(temp_str)

    try:
      txJson = json.loads(ROWS[0][-1])
    except TypeError:
      txJson = ROWS[0][-1]
    txData = ROWS[0][:-1]

    txType = ROWS[0][3]
    txValid = True if ROWS[0][7] == 'valid' else False

    #  0 - Simple send
    # 56 - Revoke Property Tokens
    # 55 - Grant Property Tokens
    # 53 - Close crowdsale
    # -1 - invalid tx
    # 21 - Metadex - TODO
    #  3 - Send to Owners - TODO

    ret = {
      "block": txData[9],
      "ecosystem": '1' if txData[5] == 'Production' else '2',
      "from_address": txJson['sendingaddress'],
      "transactionType": txData[3],
      "transactionVersion": txData[4],
      "to_address": str("(null)"),
      "confirms": txJson['confirmations'],
      "tx_hash": txData[0],
      "tx_time": (str(txJson['blocktime']) + '000') if 'blocktime' in txJson else '',
    }

    if txType not in [-22,21,25,26,27,28]: #Dex purchases don't have these fields
      ret['currencyId'] = txJson['propertyid']
      ret['currency_str'] = getName(txJson['propertyid'])
      ret['invalid'] = not txValid
      ret['amount'] = str(txJson['amount'])
      ret['formatted_amount'] = txJson['amount']
      ret['divisible'] = txJson['divisible']
      ret['fee'] = txJson['fee']
      ret['tx_type_str'] = txJson['type']

    if txType == 0 and txValid:
        ret['to_address'] = txJson['referenceaddress']

    if (txType == 50 or txType == 51 or txType == 54) and txValid:

      # 50 - Create property fixed - propertyname (getproperty), category, totaltokens, url, data, subcategory
      # 51 - Create property Variable - propertyname, (getproperty) , tokensperunit, subcategory, totaltokens, deadline,
      # category, amountraised, closedearly, propertyiddesired, maxtokens, percenttoissuer, earlybonus, active, data, url,  tokensissued, starttime
      # 54 - Create Property Manual - propertyname, (getgrants), category, totaltokens, url, [issuances], subcategory, data

      ROWS=dbSelect("select t.txhash,t.protocol,t.txdbserialnum,t.txtype,t.txversion,t.ecosystem,t.txrecvtime,t.txstate,t.txerrorcode,"
                    "t.txblocknumber,t.txseqinblock,sp.* "
                    "from transactions t, smartproperties sp where t.txhash=%s and t.txdbserialnum = sp.createtxdbserialnum", [transaction_])
      try:
        mpData = json.loads(ROWS[0][-1])
      except TypeError:
        mpData = ROWS[0][-1]

      ret['previous_property_id'] = "(null)" #TODO FIXME

      ret['propertyName'] = dehexify( mpData['name'] )
      ret['propertyCategory'] = dehexify( mpData['category'] )
      ret['propertyData'] = dehexify( mpData['data'] )
      ret['propertySubcategory'] = dehexify( mpData['subcategory'] )
      ret['propertyUrl'] = dehexify( mpData['url'] )

      ret['propertyType'] = '0002' if mpData['divisible'] == True else '0001'
      ret['formatted_property_type'] = int('0002' if mpData['divisible'] == True else '0001')

      if txType == 50 or txType == 54: ret['numberOfProperties'] = str(mpData['totaltokens']);

      if txType == 51:
        ret['numberOfProperties'] = str(mpData['tokensperunit']);
        ret['currencyIdentifierDesired'] = mpData['propertyiddesired']
        ret['deadline'] = mpData['deadline']
        ret['earlybirdBonus'] = mpData['earlybonus']
        ret['percentageForIssuer'] = mpData['percenttoissuer']

      if txType == 54: ret['issuances'] = mpData['issuances']


    if (txType == 20 or txType == 22) and txValid:

      # 20 - Dex Sell - subaction, bitcoindesired, timelimit
      # 22 - Dex Accepts - referenceaddress

      if txType == 20:
        action = 'subaction' if 'subaction' in txJson else 'action'
        cancel = True if txJson[action] == 'cancel' else False

        if not cancel:
          ROWS=dbSelect("select t.txhash,t.protocol,t.txdbserialnum,t.txtype,t.txversion,t.ecosystem,t.txrecvtime,t.txstate,t.txerrorcode,"
                        "t.txblocknumber,t.txseqinblock,ao.*,txj.txdbserialnum,txj.protocol,txj.txdata "
                        "from transactions t, activeoffers ao, txjson txj where t.txhash=%s "
                        "and t.txdbserialnum = ao.createtxdbserialnum and t.txdbserialnum=txj.txdbserialnum", [transaction_])
          row = ROWS[0]
          try:
            mpData = json.loads(ROWS[0][-1])
          except TypeError:
            mpData = ROWS[0][-1]

          ppc = Decimal( mpData['bitcoindesired'] ) / Decimal( mpData['amount'] )
          ret['amount_available'] = str(row[12])
          ret['formatted_amount_available'] = '%.8f' % ( Decimal(row[12]) / Decimal(1e8) )
          ret['bitcoin_amount_desired'] = str(row[13])
          ret['formatted_bitcoin_amount_desired'] = '%.8f' % ( Decimal(row[13]) / Decimal(1e8) )
          ret['formatted_block_time_limit'] = str(mpData['timelimit'])
          ret['formatted_fee_required'] = str(mpData['feerequired'])
          ret['formatted_price_per_coin'] = '%.8f' % ppc
          ret['bitcoin_required'] = '%.8f' % ( Decimal( ppc ) * Decimal( mpData['amount'] ) )
          ret['subaction'] = mpData[action]

        if cancel:
          ret['formatted_block_time_limit'] = str(txJson['timelimit'])
          ret['formatted_fee_required'] = str(txJson['feerequired'])
          ret['subaction'] = txJson[action]
          ret['tx_type_str'] = 'Sell cancel'

      if txType == 22:
        ROWS=dbSelect("select t.txhash,t.protocol,t.txdbserialnum,t.txtype,t.txversion,t.ecosystem,t.txrecvtime,t.txstate,t.txerrorcode,"
                      "t.txblocknumber,t.txseqinblock,oa.*,txj.txdbserialnum,txj.protocol,txj.txdata " 
                      "from transactions t, offeraccepts oa, txjson txj where t.txhash=%s "
                      "and t.txdbserialnum = oa.linkedtxdbserialnum and t.txdbserialnum=txj.txdbserialnum", [transaction_])
        try:
          mpData = json.loads(ROWS[0][-1])
        except TypeError:
          mpData = ROWS[0][-1]

        ret['to_address'] = mpData['referenceaddress']

    if (txType == -51 or txType -22) and txValid:

        #-51 - Crowdsale Purchase - purchasedpropertyid, referenceaddress, purchasedpropertydivisible, purchasedpropertyname, purchasedtokens, issuertokens, (getcrowdsale)
        #-22 - Dex Purchase - [ purchases ]

      if txType == -22:
        ret['purchases'] = txJson['purchases']
        ret['currencyId'] = '0'
        ret['currency_str'] = 'Bitcoin'
        ret['tx_type_str'] = 'Dex Purchase'

        payment = 0
        for each in ret['purchases']:
           payment += float(each['amountpaid'])
        ret['accomulated_payment'] = payment

      if txType == -51:
        ret['purchasepropertyid'] = txJson['purchasedpropertyid']
        ret['to_address'] = txJson['referenceaddress']
        ret['purchaedpropertydivisible'] = txJson['purchasedpropertydivisible']
        ret['purchasedpropertyname'] = txJson['purchasedpropertyname']
        ret['purchasedtokens'] = txJson['purchasedtokens']
        ret['issuertokens'] = txJson['issuertokens']

    return json.dumps([ ret ] , sort_keys=True, indent=4) #only send back mapped schema

def getName(propertyid):
  if int(propertyid) == 1:
    name = 'Omni Token #1'
  elif int(propertyid) == 2:
   name = 'Test Omni Token #2'
  else:
    try:
      ROWS=dbSelect("select propertyname from smartproperties where protocol='Omni' and propertyid=%s",[int(propertyid)])
      name = ROWS[0][0]+" #"+str(propertyid)
    except:
      name = "#"+str(propertyid)
  return name



def addName(txjson, list):
  #list=getpropnamelist()
  try:
    type=txjson['type_int']
  except:
    try:
      type=get_TxType(txjson['type'])
    except:
      type=-1
  if type in[0,3,20,22,53,55,56,70,185,186]:
    try:
      txjson['propertyname']=list[str(txjson['propertyid'])]['name']
      txjson['flags']=list[str(txjson['propertyid'])]['flags']
    except:
      pass
  elif type==4:
    if 'subsends' in txjson:
      for ss in txjson['subsends']:
        try:
          ss['propertyname']=list[str(ss['propertyid'])]['name']
        except:
          pass
    else:
      if 'valid' in txjson and txjson['valid']:
        print_debug(("Subsend lookup error",txjson),3)
      else:
        txjson['subsends']=[]
  elif type==-22:
    if 'purchases' in txjson:
      for p in txjson['purchases']:
        try:
          p['propertyname']=list[str(p['propertyid'])]['name']
          txjson['valid']=p['valid']
        except:
          pass
    else:
      if txjson['valid']:
        print_debug(("Purchases lookup error",txjson),3)
  elif type in [25,26]:
    try:
      txjson['propertydesired']={'name':list[str(txjson['propertyiddesired'])]['name'],'flags':list[str(txjson['propertyiddesired'])]['flags']}
      txjson['propertyforsale']={'name':list[str(txjson['propertyidforsale'])]['name'],'flags':list[str(txjson['propertyidforsale'])]['flags']}
      #deprecated after next release
      #txjson['propertyiddesiredname']=list[str(txjson['propertyiddesired'])]['name']
      #txjson['propertyidforsalename']=list[str(txjson['propertyidforsale'])]['name']
    except:
      pass
  else:
    pass
  return txjson



def get_TxType(text_type):
  try:
    convert={"Simple Send": 0 ,
             "Restricted Send": 2,
             "Send To Owners": 3,
             "Send All": 4,
             "Savings": -1,
             "Savings COMPROMISED": -1,
             "Rate-Limiting": -1,
             "Automatic Dispensary":-1,
             "DEx Sell Offer": 20,
             "MetaDEx: Offer/Accept one Master Protocol Coins for another": 21,
             "MetaDEx: Offer/Accept one Master Protocol Tokens for another": 21,
             "MetaDEx token trade": 21,
             "DEx Accept Offer": 22,
             "DEx Purchase": -22,
             "MetaDEx trade": 25,
             "MetaDEx cancel-price": 26,
             "MetaDEx cancel-pair": 27,
             "MetaDEx cancel-ecosystem": 28,
             "Create Property - Fixed": 50,
             "Create Property - Variable": 51,
             "Crowdsale Purchase": -51,
             "Promote Property": 52,
             "Close Crowdsale": 53,
             "Create Property - Manual": 54,
             "Grant Property Tokens": 55,
             "Revoke Property Tokens": 56,
             "Change Issuer Address": 70,
             "Freeze Property Tokens": 185,
             "Unfreeze Property Tokens": 186,
             "Notification": -1,
             "Feature Activation": 65534,
             "ALERT": 65535
           }
    return convert[text_type]
  except KeyError:
    return -1

