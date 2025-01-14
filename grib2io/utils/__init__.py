"""
Collection of utility functions to assist in the encoding and decoding
of GRIB2 Messages.
"""

import datetime
import numpy as np
import struct

from .. import tables

def int2bin(i, nbits=8, output=str):
    """
    Convert integer to binary string or list

    Parameters
    ----------
    **`i : int`**
        Integer value to convert to binary representation.

    **`nbits : int, optional`**
        Number of bits to return.  Valid values are 8 [DEFAULT], 16, 32, and 64.

    **`output : type`**
        Return data as `str` [DEFAULT] or `list` (list of ints).

    Returns
    -------
    `str` or `list` (list of ints) of binary representation of the integer value.
    """
    i = int(i) if not isinstance(i,int) else i
    assert nbits in [8,16,32,64]
    bitstr = "{0:b}".format(i).zfill(nbits)
    if output is str:
        return bitstr
    elif output is list:
        return [int(b) for b in bitstr]


def ieee_float_to_int(f):
    """
    Convert an IEEE 32-bit float to a 32-bit integer.

    Parameters
    ----------
    **`f : float`**
        Floating-point value.

    Returns
    -------
    `numpy.int32` representation of an IEEE 32-bit float.
    """
    i = struct.unpack('>i',struct.pack('>f',np.float32(f)))[0]
    return np.int32(i)


def ieee_int_to_float(i):
    """
    Convert a 32-bit integer to an IEEE 32-bit float.

    Parameters
    ----------
    **`i : int`**
        Integer value.

    Returns
    -------
    `numpy.float32` representation of a 32-bit int.
    """
    f = struct.unpack('>f',struct.pack('>i',np.int32(i)))[0]
    return np.float32(f)


def get_leadtime(idsec, pdtn, pdt):
    """
    Computes lead time as a datetime.timedelta object using information from
    GRIB2 Identification Section (Section 1), Product Definition Template
    Number, and Product Definition Template (Section 4).

    Parameters
    ----------
    **`idsec : list or array_like`**
        Seqeunce containing GRIB2 Identification Section (Section 1).

    **`pdtn : int`**
        GRIB2 Product Definition Template Number

    **`pdt : list or array_like`**
        Seqeunce containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------
    **`datetime.timedelta`** object representing the lead time of the GRIB2 message.
    """
    _key = {8:slice(15,21), 9:slice(22,28), 10:slice(16,22), 11:slice(18,24), 12:slice(17,23)}
    refdate = datetime.datetime(*idsec[5:11])
    try:
        return datetime.datetime(*pdt[_key[pdtn]])-refdate
    except(KeyError):
        if pdtn == 48:
            return datetime.timedelta(hours=pdt[19]*(tables.get_value_from_table(pdt[18],'scale_time_hours')))
        else:
            return datetime.timedelta(hours=pdt[8]*(tables.get_value_from_table(pdt[7],'scale_time_hours')))


def get_duration(pdtn, pdt):
    """
    Computes a time duration as a datetime.timedelta using information from
    Product Definition Template Number, and Product Definition Template (Section 4).

    Parameters
    ----------
    **`pdtn : int`**
        GRIB2 Product Definition Template Number

    **`pdt : list or array_like`**
        Sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------
    **`datetime.timedelta`** object representing the time duration of the GRIB2 message.
    """
    _key = {8:25, 9:32, 10:26, 11:28, 12:27}
    try:
        return datetime.timedelta(hours=pdt[_key[pdtn]+1]*tables.get_value_from_table(pdt[_key[pdtn]],'scale_time_hours'))
    except(KeyError):
        return None


def decode_wx_strings(lus):
    """
    Decode GRIB2 Local Use Section to obtain NDFD/MDL Weather Strings.  The
    decode procedure is defined [here](https://vlab.noaa.gov/web/mdl/nbm-gmos-grib2-wx-info).

    Parameters
    ----------
    **`lus : bytes`**
        GRIB2 Local Use Section containing NDFD weather strings.

    Returns
    -------
    **`dict`** of NDFD/MDL weather strings. Keys are an integer value that represent 
    the sequential order of the key in the packed local use section and the value is 
    the weather key.
    """
    assert lus[0] == 1
    # Unpack information related to the simple packing method
    # the packed weather string data.
    ngroups = struct.unpack('>H',lus[1:3])[0]
    nvalues = struct.unpack('>i',lus[3:7])[0]
    refvalue = struct.unpack('>i',lus[7:11])[0]
    dsf = struct.unpack('>h',lus[11:13])[0]
    nbits = lus[13]
    datatype = lus[14]
    if datatype == 0: # Floating point
        refvalue = np.float32(ieee_int_to_float(refvalue)*10**-dsf)
    elif datatype == 1: # Integer
        refvalue = np.int32(ieee_int_to_float(refvalue)*10**-dsf)
    # Upack each byte starting at byte 15 to end of the local use
    # section, create a binary string and append to the full
    # binary string.
    b = ''
    for i in range(15,len(lus)):
        iword = struct.unpack('>B',lus[i:i+1])[0]
        b += bin(iword).split('b')[1].zfill(8)
    # Iterate over the binary string (b). For each nbits
    # chunk, convert to an integer, including the refvalue,
    # and then convert the int to an ASCII character, then
    # concatenate to wxstring.
    wxstring = ''
    for i in range(0,len(b),nbits):
        wxstring += chr(int(b[i:i+nbits],2)+refvalue)
    # Return string as list, split by null character.
    #return list(filter(None,wxstring.split('\0')))
    return {n:k for n,k in enumerate(list(filter(None,wxstring.split('\0'))))}


def get_wgrib2_prob_string(probtype,sfacl,svall,sfacu,svalu):
    """
    Return a wgrib2-formatted string explaining probabilistic
    threshold informaiton.  Logic from wgrib2 source, [Prob.c](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Prob.c),
    is replicated here.

    Parameters
    ----------
    **`probtype : int`**
        Type of probability (Code Table 4.9).

    **`sfacl : int`**
        Scale factor of lower limit.

    **`svall : int`**
        Scaled value of lower limit.

    **`sfacu : int`**
        Scale factor of upper limit.

    **`svalu : int`**
        Scaled value of upper limit.

    Returns
    -------
    wgrib2-formatted string of probability threshold.
    """
    probstr = ''
    if sfacl == -127: sfacl = 0
    if sfacu == -127: sfacu = 0
    lower = svall/(10**sfacl)
    upper = svalu/(10**sfacu)
    if probtype == 0:
        probstr = 'prob <%g' % (lower)
    elif probtype == 1:
        probstr = 'prob >%g' % (upper)
    elif probtype == 2:
        if lower == upper:
            probstr = 'prob =%g' % (lower)
        else:
            probstr = 'prob >=%g <%g' % (lower,upper)
    elif probtype == 3:
        probstr = 'prob >%g' % (lower)
    elif probtype == 4:
        probstr = 'prob <%g' % (upper)
    else:
        probstr = ''
    return probstr
