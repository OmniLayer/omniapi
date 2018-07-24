#from flask import Flask, request, jsonify, abort, json
from flask_rate_limit import *
from sqltools import *
import commands
import datetime
from properties_service import rawecolist
from values_service import getCurrentPriceRaw
from cacher import *
from debug import *
from common import raw_revision

app = Flask(__name__)
app.debug = True

@app.route('/status')
@ratelimit(limit=20, per=60)
def status():
  rev=raw_revision()
  #print rev
  try:
    q=rev['last_block']
  except:
    rev={'revision':rev}

  st=raw_stats()
  #print st
  try:
    q=st['properties_count']
  except:
    st={'stats':st}

  #coms=commits().get_data()
  #print coms
  #try:
  #  coms=json.loads(coms)
  #except:
  #  coms={'commits':coms}

  #print rev, st, coms
  #merged_response = {key: value for (key, value) in (rev.items() + st.items() + coms.items())}
  merged_response = {key: value for (key, value) in (rev.items() + st.items())}
  return jsonify(merged_response)


@app.route('/revision')
@ratelimit(limit=20, per=60)
def revision():
  return jsonify(raw_revision())


@app.route('/stats')
@ratelimit(limit=20, per=60)
def stats():
  return jsonify(raw_stats())

def raw_stats():
  ckey="info:stats:stats"
  try:
    response=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select count(walletid) from wallets where walletstate='Active'")
    wallets=ROWS[0][0]

    ROWS=dbSelect("select txcount from txstats order by blocknumber desc limit 1;")
    txs=ROWS[0][0]

    txdaily=raw_txdaily()

    opc=len(rawecolist(1)['properties'])
    topc=len(rawecolist(2)['properties'])

    obtc = getCurrentPriceRaw('OMNI')['price']
    ousd = getCurrentPriceRaw('BTC')['price'] * obtc

    response = {'amount_of_wallets': wallets, 'txcount_24hr':txs, 'txdaily':txdaily, 'properties_count':opc, 'test_properties_count':topc, 'omni_btc':obtc, 'omni_usd':ousd}
    #cache 20min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,1200)

  return response


def raw_txdaily():
  ckey="info:stats:txdaily"
  try:
    ret=json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select ft.bkt,tx.txcount from txstats tx, "
                  "(select CAST(blocktime as DATE) as bkt, max(id) as id from txstats group by CAST(blocktime as date) order by bkt desc limit 15) ft "
                  "where tx.id=ft.id")
    ret=[]
    #remove first element because current day is always incomplete/invalid until tomorrow
    curday=ROWS.pop(0)
    for x in ROWS:
      ret.append({'date':str(x[0]),'count':x[1]})
    #cache until end of day
    dt = datetime.datetime.now()
    if curday[0].day == dt.day:
      #check if the newest data received is updated for today, if so cache data until end of day
      exptime=((24 - dt.hour - 1) * 60 * 60) + ((60 - dt.minute - 1) * 60) + (60 - dt.second)
    else:
      #dataset hasn't updated for the new day yet, cache for 30min to give new blocks time to come in
      exptime=1800
    lSet(ckey,json.dumps(ret))
    lExpire(ckey,exptime)
  return ret


@app.route('/commits')
@ratelimit(limit=20, per=60)
def commits():
  ckey="info:stats:commits"
  try:
    json_response = json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:  
    print_debug(("cache looked failed",ckey),7)
    owlog=commands.getoutput('git --git-dir=../.git log --pretty=tformat:"%cd | %h | %H | %s" --date=short -n 12 --no-merges')
    response=[]
    for x in owlog.split('\n'):
      y=x.split('|', 3)
      response.append({
        'date': str(y[0]),
        'commitshort': str(y[1].strip()),
        'commitlong': str(y[2].strip()),
        'msg': str(y[3].strip())
      })
    json_response = {'commits': response}
    #cache 60 min
    lSet(ckey,json.dumps(json_response))
    lExpire(ckey,3600)

  return jsonify(json_response)
