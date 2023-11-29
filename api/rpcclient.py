import requests
import time, json

class RPCHost():
    def __init__(self):
        self._session = requests.Session()
        RPCSSL=False
        RPCPORT="8332"
        RPCHOST="localhost"
        try:
            with open('/root/.omnixep/bitcoin.conf') as fp:
                for line in fp:
                    #print line
                    if line.split('=')[0] == "testnet" and line.split('=')[1] == "1":
                        RPCPORT="18332"
                    elif line.split('=')[0] == "rpcuser":
                        RPCUSER=line.split('=')[1].strip()
                    elif line.split('=')[0] == "rpcpassword":
                        RPCPASS=line.split('=')[1].strip()
                    elif line.split('=')[0] == "rpcconnect":
                        RPCHOST=line.split('=')[1].strip()
                    elif line.split('=')[0] == "rpcport":
                        RPCPORT=line.split('=')[1].strip()
                    elif line.split('=')[0] == "rpcssl":
                        if line.split('=')[1].strip() == "1":
                            RPCSSL=True
                        else:
                            RPCSSL=False
        except IOError as e:
            print('{"error": "Unable to load bitcoin config file. Please Notify Site Administrator"}')
            print 'Error %s' % e
            return None
        if RPCSSL:
            self._url = "https://"+RPCUSER+":"+RPCPASS+"@"+RPCHOST+":"+RPCPORT
        else:
            self._url = "http://"+RPCUSER+":"+RPCPASS+"@"+RPCHOST+":"+RPCPORT
        self._headers = {'content-type': 'application/json'}
    def call(self, rpcMethod, *params):
        payload = json.dumps({"method": rpcMethod, "params": list(params), "jsonrpc": "2.0"})
        tries = 2
        hadConnectionFailures = False
        while True:
            try:
                response = self._session.post(self._url, headers=self._headers, data=payload, verify=False)
            except requests.exceptions.ConnectionError:
                tries -= 1
                if tries == 0:
                    raise Exception('Failed to connect for remote procedure call.')
                hadFailedConnections = True
                print("Couldn't connect for remote procedure call, will sleep for ten seconds and then try again ({} more tries)".format(tries))
                time.sleep(10)
            else:
                if hadConnectionFailures:
                    print('Connected for remote procedure call after retry.')
                break
        if not response.status_code in (200, 500):
            raise Exception('RPC connection failure: ' + str(response.status_code) + ' ' + response.reason)
        responseJSON = response.json()
        if 'error' in responseJSON and responseJSON['error'] != None:
            raise Exception('Error in ' + rpcMethod + ' RPC call: ' + str(responseJSON['error']))
        #return responseJSON['result']
        return responseJSON



#Define / Create RPC connection
host=RPCHost()

#Bitcoin Generic RPC calls
def getinfo():
    try:
      #support omnicore v0.6
      return host.call("getblockchaininfo")
    except:
      #support omnicore v0.5
      return host.call("getinfo")

def getrawtransaction(txid):
    return host.call("getrawtransaction", txid , 1)

def getblockhash(block):
    return host.call("getblockhash", block)

def getblock(hash):
    return host.call("getblock", hash)

def sendrawtransaction(tx):
    try:
      return host.call("sendrawtransaction", tx)
    except Exception, e:
      return e

def validateaddress(addr):
    return host.call("validateaddress", addr)

def createrawtransaction(ins,outs):
    return host.call("createrawtransaction",ins,outs)

def decoderawtransaction(rawtx):
    return host.call("decoderawtransaction", rawtx)

def omni_decodetransaction(rawtx):
    return host.call("omni_decodetransaction", rawtx)

def estimateFee(blocks=4):
    try:
      #support omnicore v0.6+
      return host.call("estimatesmartfee", blocks)
    except:
      #support omnicore up to v0.5
      return host.call("estimatefee", blocks)

def gettxout(txid,vout,unconfirmed=True):
    return host.call("gettxout",txid,vout,unconfirmed)

## Omni Specific RPC calls

def omni_getactivations():
    return host.call("omni_getactivations")

def omni_getcurrentconsensushash():
    return host.call("omni_getcurrentconsensushash")

def getbalance_MP(addr, propertyid):
    return host.call("getbalance_MP", addr, propertyid)

def getallbalancesforaddress_MP(addr):
    return host.call("getallbalancesforaddress_MP", addr)

def getallbalancesforid_MP(propertyid):
    return host.call("getallbalancesforid_MP", propertyid)

def gettransaction_MP(tx):
    return host.call("gettransaction_MP", tx)

def listblocktransactions_MP(height):
    return host.call("listblocktransactions_MP", height)

def getproperty_MP(propertyid):
    return host.call("getproperty_MP", propertyid)

def listproperties_MP():
    return host.call("listproperties_MP")

def getcrowdsale_MP(propertyid):
    return host.call("getcrowdsale_MP", propertyid)

def getactivecrowdsales_MP():
    return host.call("getactivecrowdsales_MP")

def getactivedexsells_MP():
    return host.call("getactivedexsells_MP")

def getdivisible_MP(propertyid):
    return getproperty_MP(propertyid)['result']['divisible']

def getgrants_MP(propertyid):
    return host.call("getgrants_MP", propertyid)

def gettrade(txhash):
    return host.call("omni_gettrade", txhash)

def getsto_MP(txid):
    return host.call("getsto_MP", txid , "*")

def omni_listpendingtransactions():
    return host.call("omni_listpendingtransactions")

def omni_getpayload(txid):
    return host.call("omni_getpayload",txid)

def getsimplesendPayload(propertyid, amount):
    return host.call("omni_createpayload_simplesend", int(propertyid), amount)
def getsendallPayload(ecosystem):
    return host.call("omni_createpayload_sendall", int(ecosystem))
def getdexsellPayload(propertyidforsale, amountforsale, amountdesired, paymentwindow, minacceptfee, action):
    return host.call("omni_createpayload_dexsell", int(propertyidforsale), amountforsale, amountdesired, int(paymentwindow), minacceptfee, int(action))
def getdexacceptPayload(propertyid, amount):
    return host.call("omni_createpayload_dexaccept", int(propertyid), amount)
def getstoPayload(propertyid, amount):
    return host.call("omni_createpayload_sto", int(propertyid), amount)
def getgrantPayload(propertyid, amount, memo):
    return host.call("omni_createpayload_grant", int(propertyid), amount, memo)
def getrevokePayload(propertyid, amount, memo):
    return host.call("omni_createpayload_revoke", int(propertyid), amount, memo)
def getchangeissuerPayload(propertyid):
    return host.call("omni_createpayload_changeissuer", int(propertyid))
def gettradePayload(propertyidforsale, amountforsale, propertiddesired, amountdesired):
    return host.call("omni_createpayload_trade", int(propertyidforsale), amountforsale, int(propertiddesired), amountdesired)
def getissuancefixedPayload(ecosystem, divisible, previousid, category,subcategory, name, url, data, amount):
    return host.call("omni_createpayload_issuancefixed", int(ecosystem), int(divisible), int(previousid), category,subcategory, name, url, data, amount)
def getissuancecrowdsalePayload(ecosystem, divisible, previousid, category,subcategory, name, url, data, propertyiddesired, tokensperunit, deadline, earlybonus, issuerpercentage):
    return host.call("omni_createpayload_issuancecrowdsale", int(ecosystem), int(divisible), int(previousid), category,subcategory, name, url, data, int(propertyiddesired), tokensperunit, int(deadline), int(earlybonus), int(issuerpercentage))
def getissuancemanagedPayload(ecosystem, divisible, previousid, category,subcategory, name, url, data):
    return host.call("omni_createpayload_issuancemanaged", int(ecosystem), int(divisible), int(previousid), category,subcategory, name, url, data)
def getclosecrowdsalePayload(propertyid):
    return host.call("omni_createpayload_closecrowdsale", int(propertyid))
def getcanceltradesbypricePayload(propertyidforsale, amountforsale, propertiddesired, amountdesired):
    return host.call("omni_createpayload_canceltradesbyprice", int(propertyidforsale), amountforsale, int(propertiddesired), amountdesired)
def getcanceltradesbypairPayload(propertyidforsale, propertiddesired):
    return host.call("omni_createpayload_canceltradesbypair", int(propertyidforsale), int(propertiddesired))
def getcancelalltradesPayload(ecosystem):
    return host.call("omni_createpayload_cancelalltrades", int(ecosystem))
def createrawtx_opreturn(payload, rawtx=None):
    return host.call("omni_createrawtx_opreturn", rawtx, payload)
def createrawtx_multisig(payload, seed, pubkey, rawtx=None):
    return host.call("omni_createrawtx_multisig", rawtx, payload, seed, pubkey)
def createrawtx_input(txhash, index, rawtx=None):
    return host.call("omni_createrawtx_input", rawtx, txhash, index)
def createrawtx_reference(destination, rawtx=None):
    return host.call("omni_createrawtx_reference", rawtx, destination, "0.00000546")
def createrawtx_change(rawtx, previnputs, destination, fee):
    return host.call("omni_createrawtx_change", rawtx, previnputs, destination, str(fee))
 
#bitcore calls

def getaddresstxids(address):
    #Returns the txids for an address(es)
    if isinstance(address,list):
      payload = {"addresses": address}
    else:
      payload = {"addresses": [address]}
    return host.call("getaddresstxids", payload)

def getaddressdeltas(address):
    #Returns all changes for an address
    if isinstance(address,list):
      payload = {"addresses": address}
    else:
      payload = {"addresses": [address]}
    return host.call("getaddressdeltas", payload)


def getaddressbalance(address):
    #Returns the balance for an address(es)
    if isinstance(address,list):
      payload = {"addresses": address}
    else:
      payload = {"addresses": [address]}
    return host.call("getaddressbalance", payload)

def getaddressutxos(address):
    #Returns all unspent outputs for an address
    if isinstance(address,list):
      payload = {"addresses": address}
    else:
      payload = {"addresses": [address]}
    return host.call("getaddressutxos", payload)

def getaddressmempool(address):
    #Returns all mempool deltas for an address
    if isinstance(address,list):
      payload = {"addresses": address}
    else:
      payload = {"addresses": [address]}
    return host.call("getaddressmempool", payload)

def getblockhashes(start,end):
    #Returns array of hashes of blocks within the timestamp range provided
    return host.call("getblockhashes", start, end)

def getspentinfo(txid,index):
    #Returns the txid and index where an output is spent
    payload = {"txid":txid,"index":index}
    return host.call("getspentinfo", payload)