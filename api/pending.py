from decode import *
from sqltools import *
import decimal
from debug import *

def checkpendingpaymentduplicate(txhex):
  ret = False
  try:
    rawtx = decode(txhex)
  except Exception,e:
    print_debug(("Error: ", e, "\n Could not decode unsignedpretx: ", txhex),2)
    return ret

  if 'BTC' in rawtx:
    try:
      inputs=rawtx['inputs']
      sender = inputs.keys()[0]
      #unconfirmed sent txs
      ustx = dbSelect("select txdbserialnum from addressesintxs where address=%s and txdbserialnum<0 and protocol='Bitcoin' and addressrole='sender'",[sender])
      for txdbserial in ustx:
        txdbserialnum = txdbserial[0]
        if ret:
          break
        for vout in rawtx['BTC']['vout']:
          x=0
          if 'scriptPubKey' in vout:
            address = vout['scriptPubKey']['addresses'][0]
            if address == sender:
              x+=1
            else:
              q=dbSelect("select * from addressesintxs where txdbserialnum=%s and address=%s and addressrole='recipient' and protocol='Bitcoin'",(txdbserialnum,address))
              if len(q)>0:
                x+=1
        if len(vout) == x:
          ret=dbSelect("select txhash from transactions where txdbserialnum=%s",[txdbserialnum])[0][0]
    except:
      pass

  return ret

def insertpending(txhex):
  try:
    rawtx = decode(txhex)
  except Exception,e:
    print_debug(("Error: ", e, "\n Could not decode PendingTx: ", txhex),2)
    return

  if 'BTC' in rawtx:
    try:
      #handle btc pending amounts
      insertbtc(rawtx)
    except Exception,e:
      print "error inserting btc", e, "\n Could notinsert rawtx", rawtx

  error_strings = ["No Omni Layer Protocol transaction","Error in omni_decodetransaction"]
  if 'MP' in rawtx and not any(x in rawtx['MP'] for x in error_strings):
    try:
      insertomni(rawtx)
    except Exception,e:
      print "error inserting omni", e, "\n Could notinsert rawtx", rawtx

def insertbtc(rawtx):
  try:
    inputs=rawtx['inputs']
    propertyid = 0
    txtype = 0
    txversion = rawtx['BTC']['version']
    txhash = rawtx['BTC']['txid']
    protocol = "Bitcoin"
    txdbserialnum = dbSelect("select least(-1,min(txdbserialnum)) from transactions;")[0][0]
    txdbserialnum -= 1
    addresstxindex = 0

    dbExecute("insert into transactions (txhash,protocol,txdbserialnum,txtype,txversion) values(%s,%s,%s,%s,%s)",
              (txhash,protocol,txdbserialnum,txtype,txversion))

    addressrole="sender"
    for address in inputs:
      inputamount= - inputs[address]
      #insert the addressesintxs entry for the sender
      dbExecute("insert into addressesintxs (address,propertyid,protocol,txdbserialnum,addresstxindex,addressrole,balanceavailablecreditdebit) "
                "values(%s,%s,%s,%s,%s,%s,%s)", (address,propertyid,protocol,txdbserialnum,addresstxindex,addressrole,inputamount))
      addresstxindex+=1


    addresstxindex = 0
    addressrole="recipient"
    for output in rawtx['BTC']['vout']:
      outputamount = int(decimal.Decimal(str(output['value']))*decimal.Decimal(1e8))
      if output['scriptPubKey']['type'] != "nulldata":
        for addr in output['scriptPubKey']['addresses']:
           address=addr
           dbExecute("insert into addressesintxs (address,propertyid,protocol,txdbserialnum,addresstxindex,addressrole,balanceavailablecreditdebit) "
                     "values(%s,%s,%s,%s,%s,%s,%s)", (address,propertyid,protocol,txdbserialnum,addresstxindex,addressrole,outputamount))
        addresstxindex+=1

    #store signed tx until it confirms
    dbExecute("insert into txjson (txdbserialnum, protocol, txdata) values (%s,%s,%s)", (txdbserialnum, protocol, json.dumps(rawtx['BTC'])) )

    dbCommit()
  except Exception,e:
    print_debug(("Error: ", e, "\n Could not add BTC PendingTx: ", rawtx),2)
    dbRollback()

def insertomni(rawtx):
  try:
    saddressrole="sender"
    raddressrole="recipient"
    sbacd=None
    rbacd=None
    sender = rawtx['Sender']
    receiver = rawtx['Reference']
    propertyid = rawtx['MP']['propertyid'] if 'propertyid' in rawtx['MP'] else rawtx['MP']['propertyidforsale']
    txtype = rawtx['MP']['type_int']
    txversion = rawtx['MP']['version']
    txhash = rawtx['BTC']['txid']
    protocol = "Omni"
    addresstxindex=0
    txdbserialnum = dbSelect("select least(-1,min(txdbserialnum)) from transactions;")[0][0]
    txdbserialnum -= 1
    if 'amount' in rawtx['MP']:
      if rawtx['MP']['divisible']:
        amount = int(decimal.Decimal(str(rawtx['MP']['amount']))*decimal.Decimal(1e8))
      else:
        amount = int(rawtx['MP']['amount'])
    else:
      if rawtx['MP']['propertyidforsaleisdivisible']:
        amount = int(decimal.Decimal(str(rawtx['MP']['amountforsale']))*decimal.Decimal(1e8))
      else:
        amount = int(rawtx['MP']['amountforsale'])

    if txtype in [26,55]:
      #handle grants to ourself/others and cancel by price on OmniDex
      if receiver == "":
        sendamount=amount
        recvamount=0
      else:
        sendamount=0
        recvamount=amount
    elif txtype == 22:
      #sender = buyer
      saddressrole="buyer"
      sbacd=None
      #receiver = seller
      raddressrole="seller"
      rbacd=amount
      #unused in this tx
      sendamount=None
      recvamount=None
    else:
      #all other txs deduct from our balance and, where applicable, apply to the reciever
      sendamount=-amount
      recvamount=amount

    dbExecute("insert into transactions (txhash,protocol,txdbserialnum,txtype,txversion) values(%s,%s,%s,%s,%s)",
              (txhash,protocol,txdbserialnum,txtype,txversion))

    address=sender
    #insert the addressesintxs entry for the sender
    dbExecute("insert into addressesintxs (address,propertyid,protocol,txdbserialnum,addresstxindex,addressrole,balanceavailablecreditdebit,balanceacceptedcreditdebit) "
              "values(%s,%s,%s,%s,%s,%s,%s,%s)", (address,propertyid,protocol,txdbserialnum,addresstxindex,saddressrole,sendamount,sbacd))

    #update pending balance
    #dbExecute("update addressbalances set balancepending=balancepending+%s::numeric where address=%s and propertyid=%s and protocol=%s", (sendamount,address,propertyid,protocol))

    if receiver != "":
      address=receiver
      dbExecute("insert into addressesintxs (address,propertyid,protocol,txdbserialnum,addresstxindex,addressrole,balanceavailablecreditdebit,balanceacceptedcreditdebit) "
                "values(%s,%s,%s,%s,%s,%s,%s,%s)", (address,propertyid,protocol,txdbserialnum,addresstxindex,raddressrole,recvamount,rbacd))
      #update pending balance
      #dbExecute("update addressbalances set balancepending=balancepending+%s::numeric where address=%s and propertyid=%s and protocol=%s", (recvamount,address,propertyid,protocol))

    #store decoded omni data until tx confirms
    dbExecute("insert into txjson (txdbserialnum, protocol, txdata) values (%s,%s,%s)", (txdbserialnum, protocol, json.dumps(rawtx['MP'])) )

    dbCommit()
  except Exception,e:
    print_debug(("Error: ", e, "\n Could not add OMNI PendingTx: ", rawtx),2)
    dbRollback()

