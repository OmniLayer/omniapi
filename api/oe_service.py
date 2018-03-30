#from flask import Flask, request, Response, jsonify, abort, json, make_response
from flask_rate_limit import *
from bitcoin_tools import *
from get_balance import balance_propid
from transaction_service import gettxjson, getblocktxjson, getaddrhist
from property_service import getpropertyraw, getpropdistraw
from omnidex import get_orders_by_market_book_oe, get_last_price_raw, get_24hr_hist_raw, get_24hr_vol_raw
from common import raw_revision
from debug import *

app = Flask(__name__)
app.debug = True

@app.route('/requeststat.aspx', methods=['get'])
@ratelimit(limit=30, per=60)
def requeststat_aspx():
  #print request.args
  args=request.args
  if 'stat' not in args:
    return jsonify({"error":"invalid request"})

  stat=args['stat']

  if stat=='balance':
    if 'prop' not in args or 'address' not in args:
      return jsonify({"error":"invalid request"})

    prop=args['prop']
    address=args['address']
    #if is_valid_bitcoin_address(address):
      #jsonify encapsulates in a string, just return number
    return balance_propid(address,prop)
    #else:
    #  return jsonify({"error":"invalid address"})
  elif stat=='gettx':
    if 'txid' not in args:
      return jsonify({"error":"invalid request, missing txid"})
    #weird formatting, to match legacy oe need to remove curly brackets
    return json.dumps(gettxjson(args['txid']))[1:][:-1]
  elif stat=='getblocktx':
    if 'block' not in args:
      return jsonify({"error":"invalid request, missing block"})
    return jsonify(getblocktxjson(args['block']))
  else:
    return jsonify({"error":"unsupported call","args": args })


@app.route('/ask.aspx', methods=['get'])
@ratelimit(limit=30, per=60)
def ask_aspx():
  print_debug(request.args,4)
  args=request.args
  if "api" not in args:
    return jsonify({"error":"invalid request"})

  api=args['api']

  #getbalance	prop, address	Requests the available balance for a given property ID and address
  if api=="getbalance":
    if 'prop' not in args or 'address' not in args:
      return jsonify({"error":"invalid request"})

    prop=args['prop']
    address=args['address']
    #if is_valid_bitcoin_address(address):
      #jsonify encapsulates in a string, just return number
    return balance_propid(address,prop)
    #else:
    #  return jsonify({"error":"invalid address"})
 
#getreservedbalance	prop, address	Requests the reserved balance for a given property ID and address

  #getpropertybalances	prop	Requests the balances of all addresses holding tokens of a given property ID
  elif api=="getpropertybalances":
    if 'prop' not in args:
      return jsonify({"error":"invalid request, missing prop"})
    #weird formatting, to match legacy oe need to remove curly brackets
    return jsonify(getpropdistraw(args['prop']))

  #gettx	txid	Requests the transaction details for a given transaction ID
  elif api=="gettx":
    if 'txid' not in args:
      return jsonify({"error":"invalid request, missing txid"})
    #weird formatting, to match legacy oe need to remove curly brackets
    return json.dumps(gettxjson(args['txid']))[1:][:-1]

  #gettxvalidity	txid	Requests the validity of a given transaction ID
  elif api=="gettxvalidity":
    if 'txid' not in args:
      return jsonify({"error":"invalid request, missing txid"})
    #weird formatting, to match legacy oe need to remove curly brackets
    return json.dumps(gettxjson(args['txid'])['valid'])[1:][:-1]

  #gettxblock	txid	Requests the block number for a given transaction ID
  elif api=="gettxblock":
    if 'txid' not in args:
      return jsonify({"error":"invalid request, missing txid"})
    #weird formatting, to match legacy oe need to remove curly brackets
    return json.dumps(gettxjson(args['txid'])['block'])

  #gettxconfirmations	txid	Requests the number of confirmations for a given transaction ID
  elif api=="gettxconfirmations":
    if 'txid' not in args:
      return jsonify({"error":"invalid request, missing txid"})
    #weird formatting, to match legacy oe need to remove curly brackets
    return json.dumps(gettxjson(args['txid'])['confirmations'])[1:][:-1]

  #getblocktx	block	Requests the transaction details for all Omni Layer transactions in a given block
  elif api=="getblocktx":
    if 'block' not in args:
      return jsonify({"error":"invalid request, missing block"})
    return jsonify(getblocktxjson(args['block']))

  #getlastblockprocessed	-	Requests the last block processed by OmniExplorer.info
  elif api=="getlastblockprocessed":
    return json.dumps(raw_revision()['last_block'])

  #gethistory	address	Requests the historical transactions for a given address
  elif api=="gethistory":
    if 'address' not in args:
      return jsonify({"error":"invalid request"})

    address=args['address']
    #if is_valid_bitcoin_address(address):
    return jsonify( getaddrhist(address,'both'))
    #else:
    #  return jsonify({"error":"invalid address"})

  #getsenderhistory	address	Requests the historical transactions sent from a given address
  elif api=="getsenderhistory":
    if 'address' not in args:
      return jsonify({"error":"invalid request"})

    address=args['address']
    #if is_valid_bitcoin_address(address):
    return jsonify( getaddrhist(address,'send'))
    #else:
    #  return jsonify({"error":"invalid address"})

  #getrecipienthistory	address	Requests the historical transactions received by a given address
  elif api=="getrecipienthistory":
    if 'address' not in args:
      return jsonify({"error":"invalid request"})

    address=args['address']
    #if is_valid_bitcoin_address(address):
    return jsonify( getaddrhist(address,'receive'))
    #else:
    #  return jsonify({"error":"invalid address"})

  #getpropertyname	prop	Requests the display name for a given property ID
  elif api=="getpropertyname":
    try:
      if 'prop' not in args:
        raise "missing arg"
      pid=args['prop']
      raw=getpropertyraw(pid)
      return raw['name']
    except Exception, e:
      print_debug("getpropertyname error: "+str(e),4)
      return jsonify({"error":"invalid request"})

  #getpropertydivisibility	prop	Requests the divisibility for a given property ID
  elif api=="getpropertydivisibility":
    try:
      if 'prop' not in args:
        raise "missing arg"
      pid=args['prop']
      raw=getpropertyraw(pid)
      return json.dumps(raw['divisible'])
    except Exception, e:
      print_debug("getpropertydivisibility error: "+str(e),4)
      return jsonify({"error":"invalid request"})

  #getpropertytotaltokens	prop	Requests the total number of tokens for a given property ID
  elif api=="getpropertytotaltokens":
    try:
      if 'prop' not in args:
        raise "missing arg"
      pid=args['prop']
      raw=getpropertyraw(pid)
      return raw['totaltokens']
    except Exception, e:
      print_debug("getpropertytotaltokens error: "+str(e),4)
      return jsonify({"error":"invalid request"})

#getdexlastprice	-	Requests the last price of the Omni token via the Basic Distributed Exchange
#getdexorderbook	-	Requests the order book for the Omni token via the Basic Distributed Exchange
#getdexvolume24hr	-	Requests the volume of Omni token trading within the last 24 hours via the Basic Distributed Exchange
#getdexhistory24hr	-	Requests the trading history for Omni token trading within the last 24 hours via the Basic Distributed Exchange

  #getmetadexlastprice	prop, desprop	Requests the last price for a given trading pair via the Meta Distributed Exchange
  elif api=="getmetadexlastprice" or api=="getomnidexlastprice":
    if 'prop' not in args or 'desprop' not in args:
      return jsonify({"error":"invalid request"})

    try:
      prop=int(args['prop'])
      desprop=int(args['desprop'])
      response=get_last_price_raw(desprop,prop)
      return response
    except:
      return jsonify({"error":"invalid request. property id must be int"})

  #getmetadexorderbook	prop, desprop	Requests the order book for a given trading pair via the Meta Distributed Exchange
  elif api=="getmetadexorderbook" or api=="getomnidexorderbook":
    if 'prop' not in args or 'desprop' not in args:
      return jsonify({"error":"invalid request"})

    try:
      prop=int(args['prop'])
      desprop=int(args['desprop'])
      response=get_orders_by_market_book_oe(desprop,prop)
    except:
      response={"error":"invalid request. property id must be int"}
    return jsonify(response)


  #getmetadexvolume24hr	prop     Request the volume for a propertyid within last 24 hours via the Meta Distributed Exchange
  elif api=="getmetadexvolume24hr" or api=="getomnidexvolume24hr":
    if 'prop' not in args:
      return jsonify({"error":"invalid request"})

    try:
      prop=int(args['prop'])
      response=get_24hr_vol_raw(prop)
    except:
      response={"error":"invalid request. property id must be int"}
    return jsonify(response)

  #getmetadexhistory24hr	prop, desprop	Requests the trading history for a given trading pair within the last 24 hours via the Meta Distributed Exchange
  elif api=="getmetadexhistory24hr" or api=="getomnidexhistory24hr":
    if 'prop' not in args or 'desprop' not in args:
      return jsonify({"error":"invalid request"})

    try:
      prop=int(args['prop'])
      desprop=int(args['desprop'])
      response=get_24hr_hist_raw(desprop,prop)
    except:
      response={"error":"invalid request. property id must be int"}
    return jsonify(response)

#gettxcount24hr	prop(optional)	Requests the total number of transactions within the last 24 hours for the Omni Layer or a given property ID

  else:
    return jsonify({"error":"unsupported call", "args": args })

