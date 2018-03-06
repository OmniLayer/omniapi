import urlparse
import os, sys, re
#from flask import Flask, request, jsonify, abort, json, make_response, Response
from flask_rate_limit import *
from common import *
from cacher import *

app = Flask(__name__)
app.debug = True


@app.route('/<prop_id>')
def getproperty(prop_id):
  return jsonify(getpropertyraw(prop_id))

def getpropertyraw(prop_id):
  try:
    property_ = int(re.sub(r'\D+', '', prop_id.split('.')[0] ) ) #check alphanumeric
  except ValueError:
    abort(make_response('This endpoint only consumes valid input', 400))

  ckey="data:prop:"+str(prop_id)
  try:
    ret=json.loads(lGet(ckey))
  except:
    if property_ in [0,1,2]:
      ROWS=dbSelect("select propertydata from smartproperties sp where (protocol='Bitcoin' or protocol='Omni') and sp.propertyid=%s",[property_])

      try:
        ret=json.loads(ROWS[0][0])
      except TypeError:
        ret=ROWS[0][0]
    else:
      ROWS=dbSelect("select txj.txdata,sp.propertydata from txjson txj, smartproperties sp where sp.createtxdbserialnum = txj.txdbserialnum "
                    "and sp.propertyid=%s",[property_])

      try:
        txJson=json.loads(ROWS[0][0])
      except TypeError:
        txJson=ROWS[0][0]

      try:
        txData=json.loads(ROWS[0][1])
      except TypeError:
        txData=ROWS[0][1]

      ret = txJson.copy()
      ret.update(txData)

    #expire after 30 min
    lSet(ckey,json.dumps(ret))
    lExpire(ckey,1800)

  return ret

@app.route('/leg/<prop_id>')
def getpropertyleg(prop_id):
    try:
        property_ = int(re.sub(r'\D+', '', prop_id.split('.')[0] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    ROWS=dbSelect("select * from txjson txj, transactions t, smartproperties sp where sp.createtxdbserialnum = txj.txdbserialnum "
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
