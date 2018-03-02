import urlparse
import os, sys, re
import time
from flask import Flask, request, jsonify, abort, json, make_response
from common import *
from property_service import getpropertyraw
from cacher import *

data_dir_root = os.environ.get('DATADIR')

app = Flask(__name__)
app.debug = True

HISTORY_COUNT_CACHE = {}

@app.route('/categories', methods=['POST'])
def categories():
    categories_file = data_dir_root + "/www/categories.json"
    with open(categories_file, 'r') as f:
        try:
            categories = json.loads(f.read())
        except ValueError:
            print 'Error decoding JSON', categories_file.split('/')[-1][:-5]

    data = categories.keys()

    response = {
                'status' : 'OK',
                'categories' : data
                }

    return jsonify(response)

@app.route('/subcategories', methods=['POST'])
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
            print 'Error decoding JSON', categories_file.split('/')[-1][:-5]

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
def list():
  return jsonify(rawlist())

def rawlist():
  ckey="info:proplist"
  try:
    response=json.loads(lGet(ckey))
  except:
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


@app.route('/listbyecosystem', methods=['POST'])
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

  return jsonify(response)

@app.route('/listbyowner', methods=['POST'])
def listbyowner():
  # I can't believe flask can't parse properly arrays from the frontend, using values() as a hack.
  try:
      addresses = request.form.values()
  except KeyError:
      abort(make_response('No field \'issuer_addresses\' in request, request failed', 400))

  ckey="data:property:owner:"+str(addresses)
  try:
    response=json.loads(lGet(ckey))
  except:
    ROWS= dbSelect("select PropertyData from smartproperties where Protocol != 'Fiat' AND issuer= ANY(%s) ORDER BY PropertyName,PropertyID", (addresses,))
    data = [data[0] for data in ROWS]
    response = {
                'status' : 'OK',
                'properties' : data
                }
    #cache 30 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,1800)

  return jsonify(response)

@app.route('/listactivecrowdsales', methods=['POST'])
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
    response=json.loads(lGet(cket))
  except:
    ROWS= dbSelect("select PropertyData from smartproperties where PropertyData::json->>'fixedissuance'='false' AND PropertyData::json->>'active'='true' AND ecosystem=%s ORDER BY PropertyName,PropertyID", [ecosystem])
    data=[row[0] for row in ROWS]

    response = {
                'status' : 'OK',
                'crowdsales' : data
                }
    #cache 10 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,600)
  return jsonify(response)

@app.route('/getdata/<int:property_id>')
def getdata(property_id):
    return jsonify(getpropertyraw(property_id))

@app.route('/gethistory/<int:property_id>', methods=["POST"])
def gethistory(property_id):
    try:
        page = int(request.form['page'])
        offset = page * 10
    except KeyError:
      try:
        start = int(request.form['start'])
        offset = start * 10
      except KeyError:
        abort(make_response('No field \'page\' in request, request failed', 400))
      except ValueError:
        abort(make_response('Field \'page\' must be an integer, request failed', 400))
    except ValueError:
        abort(make_response('Field \'page\' must be an integer, request failed', 400))



    transactions_query = "select txjson.txdata as data from propertyhistory ph, txjson where ph.txdbserialnum =txjson.txdbserialnum and ph.propertyid=%s order by ph.txdbserialnum LIMIT 10 OFFSET %s;"
    total_query = "select count(*) as total from propertyhistory where propertyid =%s group by propertyid"

    ckey="data:property:history:count:"+str(property_id)
    try:
      total=lGet(ckey)
      if total in ['None',None]:
        raise "not cached"
    except:
      total=dbSelect(total_query,[property_id])[0][0]
      lSet(ckey,total)
      lExpire(ckey,600)

    ckey="data:property:history:txdata:"+str(property_id)+":"+str(page)
    try:
      transactions=json.loads(lGet(ckey))
    except:
      ROWS=dbSelect(transactions_query,(property_id,offset))
      transactions=[row[0] for row in ROWS]
      #cache 10 min
      lSet(ckey,json.dumps(transactions))
      lExpire(ckey,600)

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

# refactor this to be compatible with mastercored
def filterProperties( properties ):
    import glob

    addresses = glob.glob(data_dir_root + '/addr/*')
    addresses_data = []
    for prop in properties:
        for address_file in addresses:
            #print address[-5:]
            if address_file[-5:] == '.json':
                with open( address_file , 'r' ) as f:
                  try:
                    addr = json.loads(f.readline())

                    if str(prop) in addr:
                      addresses_data.append({ 'address': address_file.split('/')[-1][:-5], 'data': addr[str(prop)] })
                  except ValueError:
                    print 'Error decoding JSON', address_file.split('/')[-1][:-5]

    return ['OK',addresses_data]
