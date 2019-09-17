import urlparse
import os, sys, re
import time
#from flask import Flask, request, jsonify, abort, json, make_response
from flask_rate_limit import *
from common import *
from property_service import getpropertyraw
from cacher import *
from debug import *
import config

data_dir_root = config.LOCALDATADIR

app = Flask(__name__)
app.debug = True

HISTORY_COUNT_CACHE = {}

@app.route('/categories', methods=['POST'])
@ratelimit(limit=20, per=60)
def categories():
    categories_file = data_dir_root + "/www/categories.json"
    with open(categories_file, 'r') as f:
        try:
            categories = json.loads(f.read())
        except ValueError:
            print_debug(('Error decoding JSON', categories_file.split('/')[-1][:-5]),4)

    data = categories.keys()

    response = {
                'status' : 'OK',
                'categories' : data
                }

    return jsonify(response)

@app.route('/subcategories', methods=['POST'])
@ratelimit(limit=20, per=60)
def subcategories():
    try:
        category = request.form['category']
    except KeyError:
        abort(make_response('No field \'category\' in request, request failed', 400))

    categories_file = data_dir_root + "/www/categories.json"
    with open(categories_file, 'r') as f:
        try:
            categories = json.loads(f.read())
        except ValueError:
            print_debug(('Error decoding JSON', categories_file.split('/')[-1][:-5]),4)

    try:
        data = categories[category]
    except KeyError:
        abort(make_response('Unexisting category, request failed', 400))

    response = {
                'status' : 'OK',
                'subcategories' : data
                }

    return jsonify(response)

@app.route('/list')
@ratelimit(limit=20, per=60)
def list():
  return jsonify(rawlist())

def rawlist():
  ckey="info:proplist"
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS= dbSelect("select PropertyData from smartproperties where Protocol != 'Fiat' ORDER BY PropertyName,PropertyID")

    data=[prop[0] for prop in ROWS]

    response = {
                'status' : 'OK',
                'properties' : data
                }
    #cache property list for 30min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,1800)

  return response

def getpropnamelist(refresh=False):
  ckey="info:propnames"
  try:
    if refresh:
      raise "force refresh"
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS= dbSelect("select PropertyName,PropertyID,flags from smartproperties where Protocol != 'Fiat' ORDER BY PropertyName,PropertyID")
    response={}
    for x in ROWS:
      response[str(x[1])]={'name': x[0], 'flags':x[2]}
    #cache property list for 60min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,3600)
  return response



@app.route('/listbyecosystem', methods=['POST'])
@ratelimit(limit=20, per=60)
def listByEcosystem():
  try:
      value = int(re.sub(r'\D+', '', request.form['ecosystem']))
      valid_values = [1,2]
      if value not in valid_values:
          abort(make_response('Field \'ecosystem\' invalid value, request failed', 400))

      ecosystem = "Production" if value == 1 else "Test"
  except KeyError:
      abort(make_response('No field \'ecosystem\' in request, request failed', 400))
  except ValueError:
      abort(make_response('Field \'ecosystem\' invalid value, request failed', 400))

  return jsonify(rawecolist(value))

def rawecolist(value):
  properties = rawlist()['properties']

  pdata=[]
  for data in properties:    
    if value==2 and (data['propertyid']==2 or data['propertyid']>2147483650):
      pdata.append(data)
    elif value==1 and (data['propertyid']==1 or (data['propertyid']>2 and data['propertyid']<2147483648)):
      pdata.append(data)

  response = {
              'status' : 'OK',
              'properties' : pdata
              }

  return response

@app.route('/listbyowner', methods=['POST'])
@ratelimit(limit=20, per=60)
def listbyowner():
  # I can't believe flask can't parse properly arrays from the frontend, using values() as a hack.
  try:
      addresses = request.form.values()
  except KeyError:
      abort(make_response('No field \'issuer_addresses\' in request, request failed', 400))

  ckey="data:property:owner:"+str(addresses)
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS= dbSelect("select txj.txdata,sp.PropertyData from txjson txj, smartproperties sp  where txj.txdbserialnum=sp.createtxdbserialnum and sp.Protocol != 'Fiat' AND sp.issuer= ANY(%s) ORDER BY PropertyName,PropertyID", (addresses,))
    #ROWS= dbSelect("select PropertyData from smartproperties where Protocol != 'Fiat' AND issuer= ANY(%s) ORDER BY PropertyName,PropertyID", (addresses,))
    ret=[]
    for data in ROWS:
      x=data[0].copy()
      x.update(data[1])
      ret.append(x)
    response = {
                'status' : 'OK',
                'properties' : ret
                }
    #cache 30 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,1800)

  return jsonify(response)

@app.route('/listactivecrowdsales', methods=['POST'])
@ratelimit(limit=20, per=60)
def listcrowdsales():
  try:
      value = int(re.sub(r'\D+', '', request.form['ecosystem']))
      valid_values = [1,2]
      if value not in valid_values:
          abort(make_response('Field \'ecosystem\' invalid value, request failed', 400))

      ecosystem = "Production" if value == 1 else "Test" 
  except KeyError:
      abort(make_response('No field \'ecosystem\' in request, request failed', 400))
  except ValueError:
      abort(make_response('Field \'ecosystem\' invalid value, request failed', 400))


  ckey="data:property:crowdsale:"+str(value)
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    pnl=getpropnamelist()
    ROWS= dbSelect("select PropertyData,registrationdata,flags from smartproperties where PropertyData->>'active'='true' AND ecosystem=%s ORDER BY PropertyID", [ecosystem])
    data=[]
    for row in ROWS:
      csdata=row[0]
      rdata=row[1]
      try:
        flags=json.loads(row[2])
      except TypeError:
        flags=row[2]

      if flags in ['None',None]:
        flags={}

      if 'registered' in flags:
        csdata['registered']=flags['registered']
      else:
        csdata['registered']=False
      csdata['flags']=flags
      csdata['rdata']=rdata

      try:
        csdata['propertydesired']=pnl[str(csdata['propertyiddesired'])]
	#remove in next release
        #csdata['propertyiddesiredname']=pnl[str(csdata['propertyiddesired'])]['name']
      except:
        csdata['propertydesired']={'name':'','flags':{}}
	#remove in next release
        #csdata['propertyiddesiredname']=''
      data.append(csdata)

    response = {
                'status' : 'OK',
                'crowdsales' : data
                }
    #cache 10 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,600)
  return jsonify(response)


@app.route('/getdata/<int:property_id>')
@ratelimit(limit=20, per=60)
def getdata(property_id):
    return jsonify(getpropertyraw(property_id))

@app.route('/gethistory/<int:property_id>', methods=["POST"])
@ratelimit(limit=20, per=60)
def gethistory(property_id):
    try:
        page = int(request.form['page'])
    except KeyError:
      try:
        page = int(request.form['start'])
      except KeyError:
        abort(make_response('No field \'page\' in request, request failed', 400))
      except ValueError:
        abort(make_response('Field \'page\' must be an integer, request failed', 400))
    except ValueError:
        abort(make_response('Field \'page\' must be an integer, request failed', 400))

    #adjust page/offset so 0/1 are same starting
    page -= 1
    if page<0:
      page=0
    offset = page * 10

    rev=raw_revision()
    cblock=rev['last_block']

    transactions_query = "select txjson.txdata as data from propertyhistory ph, txjson where ph.txdbserialnum =txjson.txdbserialnum and ph.propertyid=%s order by ph.txdbserialnum LIMIT 10 OFFSET %s;"
    total_query = "select count(*) as total from propertyhistory where propertyid =%s group by propertyid"

    ckey="data:property:history:count:"+str(property_id)
    try:
      total=int(lGet(ckey))
      if total in ['None',None]:
        raise "not cached"
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      total=dbSelect(total_query,[property_id])[0][0]
      lSet(ckey,total)
      lExpire(ckey,600)

    ckey="data:property:history:txdata:"+str(property_id)+":"+str(page)
    try:
      transactions=json.loads(lGet(ckey))
      print_debug(("cache looked success",ckey),7)
    except:
      print_debug(("cache looked failed",ckey),7)
      ROWS=dbSelect(transactions_query,(property_id,offset))
      transactions=[row[0] for row in ROWS]
      #cache 10 min
      lSet(ckey,json.dumps(transactions))
      lExpire(ckey,600)

    try:
      for tx in transactions:
        tx['confirmations'] = cblock - tx['block'] + 1
    except:
      pass

    response = {
                "total" : total,
                "pages" : total/10,
                "transactions" : transactions
                }
    return jsonify(response)


#deprecated/invalid source
#@app.route('/info', methods=['POST'])
def prinfo():
    try:
        property_ = request.form['property']
    except KeyError:
        abort(make_response('No field \'property\' in request, request failed', 400))

    try:
        property_ = json.loads(property_)
    except ValueError:
        abort(make_response('This endpoint only consumes valid JSON', 400))

    if type(property_) != type([]) or len(property_) == len([]):
        abort(make_response('Please provide data in a JSON array for processing, request failed', 400))

    for prop in property_:
        if type(prop) != type(0):
            abort(make_response('Array data must be of type int', 400))
        #property_ = map(( lambda prop_: re.sub('\D','', prop_ ) ), property_ )

    data = filterProperties(property_)

    response={
        'status': data[0],
        'data': data[1]
        }

    #DEBUG print response
    return jsonify(response)
