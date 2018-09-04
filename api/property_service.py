import urlparse
import os, sys, re
#from flask import Flask, request, jsonify, abort, json, make_response, Response
from flask_rate_limit import *
from common import *
from cacher import *
from debug import *
from decimal import Decimal

app = Flask(__name__)
app.debug = True


@app.route('/<prop_id>')
@ratelimit(limit=20, per=60)
def getproperty(prop_id):
  return jsonify(getpropertyraw(prop_id))

def getpropertyraw(prop_id):
  try:
    property_ = int(re.sub(r'\D+', '', str(prop_id).split('.')[0] ) ) #check alphanumeric
  except ValueError:
    abort(make_response('This endpoint only consumes valid input', 400))

  ckey="data:prop:"+str(property_)
  try:
    ret=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    if property_ in [0,1,2]:
      ROWS=dbSelect("select propertydata,registrationdata,flags from smartproperties sp where (protocol='Bitcoin' or protocol='Omni') and sp.propertyid=%s",[property_])

      try:
        ret=json.loads(ROWS[0][0])
      except TypeError:
        ret=ROWS[0][0]

      rdata=ROWS[0][1]

      try:
        flags=json.loads(ROWS[0][2])
      except TypeError:
        flags=ROWS[0][2]

    else:
      ROWS=dbSelect("select txj.txdata,sp.propertydata,sp.registrationdata,sp.flags from txjson txj, smartproperties sp where sp.createtxdbserialnum = txj.txdbserialnum "
                    "and sp.propertyid=%s",[property_])

      try:
        txJson=json.loads(ROWS[0][0])
      except TypeError:
        txJson=ROWS[0][0]

      try:
        txData=json.loads(ROWS[0][1])
      except TypeError:
        txData=ROWS[0][1]

      rdata=ROWS[0][2]

      try:
        flags=json.loads(ROWS[0][3])
      except TypeError:
        flags=ROWS[0][3]

      ret = txJson.copy()
      ret.update(txData)

    if flags in ['None',None]:
      flags={}

    if 'registered' in flags:
      ret['registered']=flags['registered']
    else:
      ret['registered']=False
    ret['flags']=flags
    ret['rdata']=rdata

    #expire after 30 min
    lSet(ckey,json.dumps(ret))
    lExpire(ckey,1800)

  return ret

#@app.route('/leg/<prop_id>')
#@ratelimit(limit=11, per=60)
def getpropertyleg(prop_id):
    try:
        property_ = int(re.sub(r'\D+', '', prop_id.split('.')[0] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    ROWS=dbSelect("select txj.txdbserialnum,txj.protocol,txj.txdata,t.txhash,t.protocol,t.txdbserialnum,t.txtype,t.txversion,t.ecosystem,t.txrecvtime,t.txstate,t.txerrorcode,"
                  "t.txblocknumber,t.txseqinblock,sp.* from txjson txj, transactions t, smartproperties sp where sp.createtxdbserialnum = txj.txdbserialnum "
                  "and sp.createtxdbserialnum = t.txdbserialnum and sp.propertyid=%s",[property_])

    #print property_, ROWS[0]

    def dehexify(hex_str):
        temp_str=[]
        for let in hex_str:
            if ord(let) < 128:
                temp_str.append(let)
            else:
                temp_str.append('?')
        return ''.join(temp_str)

    dbtxJson = ROWS[0][:3]
    try:
      txJson=json.loads(dbtxJson[-1])
    except TypeError:
      txJson=dbtxJson[-1]

    ROWS = [ ROWS[0][3:] ]

    txData = ROWS[0][:-1]
    try:
      mpData = json.loads(ROWS[0][-1])
    except TypeError:
      mpData = ROWS[0][-1]

    txType = txData[3]

    #map tx 50,51, and 54 data into this data blob
    ret = {
      "block": txData[9],
      "currencyId": mpData['propertyid'],
      "currency_str": "Smart Property",
      "ecosystem": '1' if txData[5] == 'Production' else '2',
      "from_address": txData[13],
      "previous_property_id": "(null)", #TODO FIXME
      "propertyCategory": dehexify( mpData['category'] ),
      "propertyData": dehexify( mpData['data'] ),
      "propertyName": dehexify( mpData['name'] ),
      "propertySubcategory": dehexify( mpData['subcategory'] ),
      "propertyUrl": dehexify( mpData['url'] ),
      "propertyType": '0002' if mpData['divisible'] == True else '0001',
      "formatted_property_type": int('0002' if mpData['divisible'] == True else '0001'),
      "transactionType": txData[3],
      "transactionVersion": txData[4],
      "tx_hash": txData[0],
      "tx_time": txJson['blocktime']
    }

    if txType == 50: ret['numberOfProperties'] = mpData['totaltokens'];

    if txType == 51:
      ret['numberOfProperties'] = mpData['tokensperunit'];
      ret['currencyIdentifierDesired'] = mpData['propertyiddesired']
      ret['deadline'] = mpData['deadline']
      ret['earlybirdBonus'] = mpData['earlybonus']
      ret['percentageForIssuer'] = mpData['percenttoissuer']

    if txType == 54:
      ret['numberOfProperties'] = mpData['totaltokens'];
      ret['issuances'] = mpData['issuances']

    #Fields that didn't make it, may become relevant at a later time

    #"tx_type_str": "Fundraiser property creation"
    #"formatted_amount": 0,
    #"formatted_ecosystem": 1,
    #"formatted_previous_property_id": 0,
    #"formatted_transactionType": 51,
    #"formatted_transactionVersion": 0,
    #"baseCoin": "00",
    #"color": "bgc-new",
    #"dataSequenceNum": "01",
    #"details": "unknown",
    #"icon": "unknown",
    #"index": "215",
    #"invalid": false,
    #"method": "multisig",
    #"to_address": "1ARjWDkZ7kT9fwjPrjcQyvbXDkEySzKHwu",
    #"tx_method_str": "multisig",
    #"update_fs": false


    return Response(json.dumps([ret]), mimetype="application/json") #only send back mapped schema

@app.route('/distribution/<prop_id>', methods=['GET'])
@ratelimit(limit=20, per=60)
def getpropdist(prop_id):
  return jsonify(getpropdistraw(prop_id))

def getpropdistraw(prop_id):
  try:
    property_ = int(re.sub(r'\D+', '', str(prop_id).split('.')[0] ) ) #check alphanumeric
  except ValueError:
    abort(make_response('This endpoint only consumes valid input', 400))

  rev=raw_revision()
  cblock=rev['last_block']

  ckey="data:property:dist:"+str(cblock)+":"+str(property_)
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS= dbSelect("select address, balanceavailable, balancereserved, balancefrozen from addressbalances where propertyid=%s and protocol='Omni' and (balanceavailable>0 or balancereserved>0 or balancefrozen>0)", [property_])

    response=[]
    divisible=getpropertyraw(str(property_))['divisible']
    for row in ROWS:
      frozen=row[3]
      if(divisible):
        bal = str( Decimal(row[1]) / Decimal(1e8) )
        resv = str( Decimal(row[2]) / Decimal(1e8) )
        frz = str( Decimal(row[3]) / Decimal(1e8) )
      else:
        bal = str(row[1])
        resv = str(row[2])
        frz = str(row[3])
      if frozen == 0:
        resp={'address' : row[0], 'balance' : bal, 'reserved' : resv}
      else:
        resp={'address' : row[0], 'balance' : frz, 'reserved' : resv, 'frozen' : True}
      response.append(resp)
    #cache 60 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,3600)
  return response

