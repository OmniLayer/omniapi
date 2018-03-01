#import hashlib
#import re
from pycoin import encoding
from pybitcointools import pubtoaddr
#from ecdsa import curves, ecdsa

__b58chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
__b58base = len(__b58chars)
max_currency_value=21000000
dust_limit=546

def formatted_decimal(float_number):
    s=str("{0:.8f}".format(float_number))
    if s.strip('0.') == '':      # only zero and/or decimal point
        return '0.0'
    else:
        trimmed=s.rstrip('0')     # remove zeros on the right
        if trimmed.endswith('.'): # make sure there is at least one zero on the right
            return trimmed+'0'
        else:
            if trimmed.find('.')==-1:
                return trimmed+'.0'
            else:
                return trimmed

def to_satoshi(value):
    return int(float(value)*1e8)

def from_satoshi(value):
    float_number=int(value)/1e8
    return formatted_decimal(float_number)

def bc_address_to_hash_160(addr):
    vh160_with_checksum=b58decode(addr, 25)
    return vh160_with_checksum[1:-4]

def b58decode(v, length):
    """ decode v into a string of len bytes """
    long_value = 0L
    for (i, c) in enumerate(v[::-1]):
      long_value += __b58chars.find(c) * (__b58base**i)
    result = ''
    while long_value >= 256:
        div, mod = divmod(long_value, 256)
        result = chr(mod) + result
        long_value = div
    result = chr(long_value) + result
    nPad = 0
    for c in v:
        if c == __b58chars[0]: nPad += 1
        else: break
    result = chr(0)*nPad + result
    if length is not None and len(result) != length:
        return None
    return result

def is_pubkey_valid(pubkey):
    try:
        return encoding.is_valid_bitcoin_address(pubtoaddr(pubkey))
    except:
        return False

def is_valid_bitcoin_address(addr):
    try:
        return encoding.is_valid_bitcoin_address(addr)
    except:
        return False

def is_valid_bitcoin_address_or_pubkey(value):
    return is_valid_bitcoin_address or is_pubkey_valid(value)

