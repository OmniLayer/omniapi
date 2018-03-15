import urlparse
import os, sys, re
import math
#from flask import Flask, request, Response, jsonify, abort, json, make_response
from flask_rate_limit import *
from common import *
from decimal import Decimal
from blockchain_utils import *
from stats_service import raw_revision
from cacher import *
from properties_service import getpropnamelist
from debug import *

app = Flask(__name__)
app.debug = True

@app.route('/estimatefee/<addr>', methods=['GET','POST'])
@ratelimit(limit=20, per=60)
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
@ratelimit(limit=20, per=60)
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
@ratelimit(limit=20, per=60)
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


def getaddresshistraw(address,page):
    rev=raw_revision()
    cblock=rev['last_block']

    try:
      page=int(page)
    except:
      page=1

    page-=1
    if page<0:
      page=0

    toadd=[]
    limit=10
    offset=page*10
    ckey="data:addrhist:"+str(address)+":"+str(page)
    try:
      #check cache
      txlist = json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)

      raw=getrawpending()
      try:
        pending=raw['index'][address]
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
        print_debug(("getaddresshistraw pending inject failed",e),2)
        pass

      ROWS=dbSelect("select txj.txdata from txjson txj, addressesintxs atx where atx.txdbserialnum=txj.txdbserialnum and atx.address=%s and txj.txdbserialnum > 0 order by txj.txdbserialnum desc limit %s offset %s",(address,limit,offset))
      #set and cache data for 7 min
      pnl=getpropnamelist()
      txlist=[]
      for r in ROWS:
        txJson=addName(r[0],pnl)
        txlist.append(txJson)
      txlist = toadd+txlist
      lSet(ckey,json.dumps(txlist))
      lExpire(ckey,420)

    try:
      for tx in txlist:
        tx['confirmations'] = cblock - tx['block'] + 1
    except:
      pass

    cachetxs(txlist)
    pcount=getaddresstxcount(address)
    response = { 'address': address, 'transactions': txlist , 'pages': pcount}

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
    ROWS=dbSelect("select count(txdbserialnum) from txjson;")
    count=int(ROWS[0][0])
    #cache 10 min
    lSet(ckey,count)
    lExpire(ckey,600)

  return (count/limit)

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
    ROWS=dbSelect("select count(txdbserialnum) from addressesintxs where address=%s;",[address])
    count=int(ROWS[0][0])
    lSet(ckey,count)
    lExpire(ckey,600)

  return (count/limit)


@app.route('/general/')
@ratelimit(limit=20, per=60)
def getrecenttx():
  return getrecenttxpages()

@app.route('/general/<page>')
@ratelimit(limit=20, per=60)
def getrecenttxpages(page=1):
    #pagination starts at 1 so adjust accordingly to treat page 0 and 1 the same
    try:
      page=int(page)
    except:
      page=1

    page-=1
    if page < 0:
      page=0

    try:
      offset=int(page)*10
    except:
      offset=0
      page=0

    rev=raw_revision()
    cblock=rev['last_block']
    toadd=[]
    limit=10

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


      ROWS=dbSelect("select txdata from txjson txj where protocol = 'Omni' and txdbserialnum > 0 order by txdbserialnum DESC offset %s limit %s;",(offset,limit))
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
        #check if tx is unconfirmed and expire cache after 5 min if it is
        if tx['confirmations'] == 0:
          lExpire(ckey,300)
      except:
        print_debug(("error expiring",ckey,tx),2)
        lExpire(ckey,300)

def getrawpending():
    ckey="data:tx:pendinglist"
    try:
      response=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect("select txj.txdata, extract(epoch from tx.txrecvtime) from txjson txj,transactions tx where tx.txdbserialnum=txj.txdbserialnum and txj.protocol = 'Omni' and txj.txdbserialnum < 0 order by txdbserialnum DESC;")
      data = []
      index = {}
      pnl=getpropnamelist()
      if len(ROWS) > 0:
        for d in ROWS:
          res = addName(d[0],pnl)
          res['blocktime']=int(d[1])
          data.append(res)
          try:
            index[res['referenceaddress']].append(res)
          except:
            index[res['referenceaddress']]=[res]
      response={'data':data,'index':index}
      #cache for 5 min
      lSet(ckey,json.dumps(response))
      lExpire(ckey,300)
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
      txJson=lGet(json.loads(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect("select txj.txdata from transactions t, txjson txj where t.txdbserialnum = txj.txdbserialnum and t.protocol != 'Bitcoin' and t.txhash=%s", [transaction_])
      if len(ROWS) < 1:
        return json.dumps([])
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
      lSet(ckey,json.dumps(txJson))
      try:
        #check if tx is unconfirmed and expire cache after 5 min if it is
        if txJson['confirmations'] == 0:
          lExpire(ckey,300)
      except:
        lExpire(ckey,300)

    try:
      if 'type_int' not in txJson and txJson['type']=="DEx Purchase":
        txJson['type_int']=-22
    except:
      pass
    try:
      txJson['confirmations'] = cblock - txJson['block'] + 1
    except:
      pass

    #if cblock hasn't caught up make sure we don't return negative weirdness
    if txJson['confirmations'] < 0:
      txJson['confirmations'] = 0

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
    #cache for 1 min
    lSet(ckey,bhash)
    lExpire(ckey,60)

  return bhash

def getblocktxjson(block):
  bhash=getblockhash(block)
  if "error" in bhash:
    return bhash

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

    response = {"block":block_, "blockhash":bhash, "transactions": ret}
    #cache for 30 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,1800)
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

    ROWS=dbSelect("select * from transactions t, txjson txj where t.txdbserialnum = txj.txdbserialnum and t.protocol != 'Bitcoin' and t.txhash=%s", [transaction_])

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
      ret['currency_str'] = 'Omni' if txJson['propertyid'] == 1 else 'Test Omni' if txJson['propertyid'] == 2 else "Smart Property"
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

      ROWS=dbSelect("select * from transactions t, smartproperties sp where t.txhash=%s and t.txdbserialnum = sp.createtxdbserialnum", [transaction_])
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
          ROWS=dbSelect("select * from transactions t, activeoffers ao, txjson txj where t.txhash=%s "
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
        ROWS=dbSelect("select * from transactions t, offeraccepts oa, txjson txj where t.txhash=%s "
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



def addName(txjson, list):
  #list=getpropnamelist()
  type=txjson['type_int']
  if type in[0,3,20,22,53,55,56,70,185,186]:
    txjson['propertyname']=list[str(txjson['propertyid'])]
  elif type==4:
    for ss in txjson['subsends']:
      ss['propertyname']=list[str(ss['propertyid'])]
  elif type==-22:
    for p in txjson['purchases']:
      p['propertyname']=list[str(p['propertyid'])]
      txjson['valid']=p['valid']
  elif type in [25,26]:
    txjson['propertyiddesiredname']=list[str(txjson['propertyiddesired'])]
    txjson['propertyidforsalename']=list[str(txjson['propertyidforsale'])]
  else:
    pass

  return txjson
