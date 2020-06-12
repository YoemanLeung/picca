#!/usr/bin/python3
"""Compute the cross-covariance matrix between two correlations."""
import argparse
import sys
import numpy as np
import scipy.linalg
import fitsio

from picca.utils import compute_cov, userprint

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=('Compute the cross-covariance matrix between two '
                     'correlations'))

    parser.add_argument(
        '--data1',
        type=str,
        default=None,
        required=True,
        help='Correlation 1 produced via picca_cf.py, picca_xcf.py, ...')

    parser.add_argument(
        '--data2',
        type=str,
        default=None,
        required=True,
        help='Correlation 2 produced via picca_cf.py, picca_xcf.py, ...')

    parser.add_argument('--out',
                        type=str,
                        default=None,
                        required=True,
                        help='Output file name')

    args = parser.parse_args()

    data = {}

    ### Read data
    for i,p in enumerate([args.data1,args.data2]):
        h = fitsio.FITS(p)
        head = h[1].read_header()
        nside = head['NSIDE']
        head = h[2].read_header()
        scheme = head['HLPXSCHM']
        da  = sp.array(h[2]['DA'][:])
        weights  = sp.array(h[2]['WE'][:])
        hep = sp.array(h[2]['HEALPID'][:])
        data[i] = {'DA':da, 'WE':weights, 'HEALPID':hep, 'NSIDE':nside, 'HLPXSCHM':scheme}
        h.close()

    ### exit if NSIDE1!=NSIDE2
    if data[0]['NSIDE']!=data[1]['NSIDE']:
        userprint("ERROR: NSIDE are different: {} != {}".format(data[0]['NSIDE'],data[1]['NSIDE']))
        sys.exit()
    ### exit if HLPXSCHM1!=HLPXSCHM2
    if data[0]['HLPXSCHM']!=data[1]['HLPXSCHM']:
        userprint("ERROR: HLPXSCHM are different: {} != {}".format(data[0]['HLPXSCHM'],data[1]['HLPXSCHM']))
        sys.exit()

    ### Add unshared healpix as empty data
    for i in sorted(list(data.keys())):
        j = (i+1)%2
        w = np.logical_not( sp.in1d(data[j]['HEALPID'],data[i]['HEALPID']) )
        if w.sum()>0:
            new_healpix = data[j]['HEALPID'][w]
            nb_new_healpix = new_healpix.size
            nb_bins = data[i]['DA'].shape[1]
            userprint("Some healpix are unshared in data {}: {}".format(i,new_healpix))
            data[i]['DA']      = sp.append(data[i]['DA'],np.zeros((nb_new_healpix,nb_bins)),axis=0)
            data[i]['WE']      = sp.append(data[i]['WE'],np.zeros((nb_new_healpix,nb_bins)),axis=0)
            data[i]['HEALPID'] = sp.append(data[i]['HEALPID'],new_healpix)

    ### Sort the data by the healpix values
    for i in sorted(list(data.keys())):
        sort = sp.array(data[i]['HEALPID']).argsort()
        data[i]['DA']      = data[i]['DA'][sort]
        data[i]['WE']      = data[i]['WE'][sort]
        data[i]['HEALPID'] = data[i]['HEALPID'][sort]

    ### Append the data
    da  = sp.append(data[0]['DA'],data[1]['DA'],axis=1)
    weights  = sp.append(data[0]['WE'],data[1]['WE'],axis=1)

    ### Compute the covariance
    covariance = compute_cov(da,weights)

    ### Get the cross-covariance
    size1 = data[0]['DA'].shape[1]
    cross_co = covariance.copy()
    cross_co = cross_co[:,size1:]
    cross_co = cross_co[:size1,:]

    ### Get the cross-correlation
    var = sp.diagonal(covariance)
    cor = covariance/sp.sqrt(var*var[:,None])
    cross_cor = cor.copy()
    cross_cor = cross_cor[:,size1:]
    cross_cor = cross_cor[:size1,:]

    ### Test if valid
    try:
        scipy.linalg.cholesky(covariance)
    except scipy.linalg.LinAlgError:
        userprint('WARNING: Matrix is not positive definite')

    ### Save
    h = fitsio.FITS(args.out,'rw',clobber=True)
    h.write([cross_co,cross_cor],names=['CO','COR'],comment=['Covariance matrix','Correlation matrix'],extname='COVAR')
    h.close()
