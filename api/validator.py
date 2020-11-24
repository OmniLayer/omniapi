from hashlib import sha256
import config

BTC_B58Chars = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

if bytes == str:  # python2
    bseq = lambda s: ''.join(map(chr, s))
else:  # python3
    bseq = bytes

try:
  TESTNET = (config.TESTNET == 1)
except:
  TESTNET = False


def isvalid(address):
    ret = False

    if TESTNET:
      checkset = ['m','n','2']
    else:
      checkset = ['1','3']

    try:
      if str(address[0]) in checkset:
        ret = (b58decode_check(address) != None)
    except:
      pass
    return ret

def scrub_input(v):
    if isinstance(v, str) and not isinstance(v, bytes):
        v = v.encode('ascii')
    return v

def b58decode_int(v, alphabet=BTC_B58Chars):
    """
    Decode a Base58 encoded string as an integer
    """
    v = v.rstrip()
    v = scrub_input(v)
    decimal = 0
    for char in v:
        decimal = decimal * 58 + alphabet.index(char)
    return decimal

def b58decode(v, alphabet=BTC_B58Chars):
    """
    Decode a Base58 encoded string
    """
    v = v.rstrip()
    v = scrub_input(v)
    origlen = len(v)
    v = v.lstrip(alphabet[0:1])
    newlen = len(v)
    acc = b58decode_int(v, alphabet=alphabet)
    result = []
    while acc > 0:
        acc, mod = divmod(acc, 256)
        result.append(mod)
    return b'\0' * (origlen - newlen) + bseq(reversed(result))

def b58decode_check(v, alphabet=BTC_B58Chars):
    '''Decode and verify the checksum of a Base58 encoded string'''
    result = b58decode(v, alphabet=alphabet)
    result, check = result[:-4], result[-4:]
    digest = sha256(sha256(result).digest()).digest()
    if check != digest[:4]:
        raise ValueError("Invalid checksum")
    return result
