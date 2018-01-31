#!/usr/bin/env python

import scipy as sp
import fitsio
import argparse
import glob
import healpy
import sys
from scipy import random 
from scipy.interpolate import interp1d
import copy 

from picca import constants
from picca import cf
from picca.data import delta

from multiprocessing import Pool,Process,Lock,Manager,cpu_count,Value


def calc_dmat(p):
    if x_correlation: 
        cf.fill_neighs_x_correlation(p)
    else: 
        cf.fill_neighs(p)
    tmp = cf.dmat(p)
    return tmp

if __name__ == '__main__':

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--out', type = str, default = None, required=True,
                        help = 'output file name')

    parser.add_argument('--in-dir', type = str, default = None, required=True,
                        help = 'data directory')

    parser.add_argument('--in-dir2', type = str, default = None, required=False,
                        help = 'second delta directory')

    parser.add_argument('--rp-max', type = float, default = 200., required=False,
                        help = 'max rp [h^-1 Mpc]')

    parser.add_argument('--rp-min', type = float, default = 0., required=False,
                        help = 'min rp [h^-1 Mpc]')

    parser.add_argument('--rt-max', type = float, default = 200., required=False,
                        help = 'max rt [h^-1 Mpc]')

    parser.add_argument('--np', type = int, default = 50, required=False,
                        help = 'number of r-parallel bins')

    parser.add_argument('--nt', type = int, default = 50, required=False,
                        help = 'number of r-transverse bins')

    parser.add_argument('--lambda-abs', type = str, default = 'LYA', required=False,
                        help = 'name of the absorption in picca.constants')

    parser.add_argument('--lambda-abs2', type = str, default = None, required=False,
                        help = 'name of the 2nd absorption in picca.constants')

    parser.add_argument('--fid-Om', type = float, default = 0.315, required=False,
                    help = 'Om of fiducial cosmology')

    parser.add_argument('--nside', type = int, default = 8, required=False,
                    help = 'healpix nside')

    parser.add_argument('--nproc', type = int, default = None, required=False,
                    help = 'number of processors')

    parser.add_argument('--z-ref', type = float, default = 2.25, required=False,
                    help = 'reference redshift')

    parser.add_argument('--rej', type = float, default = 1., required=False,
                    help = 'reference redshift')

    parser.add_argument('--z-evol', type = float, default = 2.9, required=False,
                    help = 'exponent of the redshift evolution of the delta field')

    parser.add_argument('--z-evol2', type = float, default = 2.9, required=False,
                    help = 'exponent of the redshift evolution of the 2nd delta field')

    parser.add_argument('--nspec', type=int,default=None, required=False,
                    help = 'maximum spectra to read')

    parser.add_argument('--no-project', action="store_true", required=False,
                    help = 'do not project out continuum fitting modes')

    parser.add_argument('--no-same-wavelength-pairs', action="store_true", required=False,
                    help = 'Reject pairs with same wavelength')

    args = parser.parse_args()

    if args.nproc is None:
        args.nproc = cpu_count()//2

    print("nproc",args.nproc)

    cf.rp_max = args.rp_max
    cf.rp_min = args.rp_min
    cf.rt_max = args.rt_max
    cf.np = args.np
    cf.nt = args.nt
    cf.nside = args.nside
    cf.zref = args.z_ref
    cf.alpha = args.z_evol
    cf.lambda_abs = args.lambda_abs
    cf.rej = args.rej
    cf.no_same_wavelength_pairs = args.no_same_wavelength_pairs

    cosmo = constants.cosmo(args.fid_Om)

    lambda_abs = constants.absorber_IGM[args.lambda_abs]
    if args.lambda_abs2: lambda_abs2 = constants.absorber_IGM[args.lambda_abs2]
    else: lambda_abs2 = constants.absorber_IGM[args.lambda_abs]

    z_min_pix = 1.e6
    ndata=0
    if (len(args.in_dir)>8) and (args.in_dir[-8:]==".fits.gz"):
        fi = glob.glob(args.in_dir)
    else:
        fi = glob.glob(args.in_dir+"/*.fits.gz")
    fi = sorted(fi)
    data = {}
    dels = []
    for i,f in enumerate(fi):
        sys.stderr.write("\rread {} of {} {}".format(i,len(fi),ndata))
        hdus = fitsio.FITS(f)
        dels += [delta.from_fitsio(h) for h in hdus[1:]]
        ndata+=len(hdus[1:])
        hdus.close()
        if not args.nspec is None:
            if ndata>args.nspec:break
    sys.stderr.write("read {}\n".format(ndata))

    x_correlation=False
    if args.in_dir2: 
        x_correlation=True
        ndata2 = 0
        if (len(args.in_dir2)>8) and (args.in_dir2[-8:]==".fits.gz"):
            fi = glob.glob(args.in_dir2)
        else:
            fi = glob.glob(args.in_dir2+"/*.fits.gz")
        fi = sorted(fi)
        data2 = {}
        dels2 = []
        for i,f in enumerate(fi):
            sys.stderr.write("\rread {} of {} {}".format(i,len(fi),ndata))
            hdus = fitsio.FITS(f)
            dels2 += [delta.from_fitsio(h) for h in hdus[1:]]
            ndata2+=len(hdus[1:])
            hdus.close()
            if not args.nspec is None:
                if ndata2>args.nspec:break
        sys.stderr.write("read {}\n".format(ndata2))

    elif lambda_abs != lambda_abs2:   
        x_correlation=True
        data2  = copy.deepcopy(data)
        ndata2 = copy.deepcopy(ndata)
        dels2  = copy.deepcopy(dels)
    cf.x_correlation=x_correlation 
    if x_correlation: print("doing xcorrelation")
 
    z_min_pix = 10**dels[0].ll[0]/lambda_abs-1.
    phi = [d.ra for d in dels]
    th = [sp.pi/2.-d.dec for d in dels]
    pix = healpy.ang2pix(cf.nside,th,phi)
    for d,p in zip(dels,pix):
        if not p in data:
            data[p]=[]
        data[p].append(d)

        z = 10**d.ll/lambda_abs-1.
        z_min_pix = sp.amin( sp.append([z_min_pix],z) )
        d.z = z
        d.r_comov = cosmo.r_comoving(z)
        d.we *= ((1.+z)/(1.+args.z_ref))**(cf.alpha-1.)
        if not args.no_project:
            d.project()

    cf.angmax = 2.*sp.arcsin(cf.rt_max/(2.*cosmo.r_comoving(z_min_pix)))
    
    if x_correlation: 
        cf.alpha2 = args.z_evol2
        z_min_pix2 = 10**dels2[0].ll[0]/lambda_abs2-1.
        phi2 = [d.ra for d in dels2]
        th2 = [sp.pi/2.-d.dec for d in dels2]
        pix2 = healpy.ang2pix(cf.nside,th2,phi2)

        for d,p in zip(dels2,pix2):
            if not p in data2:
                data2[p]=[]
            data2[p].append(d)

            z = 10**d.ll/lambda_abs2-1.
            z_min_pix2 = sp.amin(sp.append([z_min_pix2],z) )
            d.z = z
            d.r_comov = cosmo.r_comoving(z)
            d.we *= ((1.+z)/(1.+args.z_ref))**(cf.alpha2-1.)
            if not args.no_project:
                d.project()

        cf.angmax = 2.*sp.arcsin(cf.rt_max/( cosmo.r_comoving(z_min_pix)+cosmo.r_comoving(z_min_pix2) ))

    cf.npix = len(data)
    cf.data = data
    cf.ndata = ndata
    if x_correlation: 
       cf.data2 = data2 
       cf.ndata2 = ndata2 
    print("done")

    cf.counter = Value('i',0)

    cf.lock = Lock()
    
    cpu_data = {}
    for i,p in enumerate(sorted(list(data.keys()))):
        ip = i%args.nproc
        if not ip in cpu_data:
            cpu_data[ip] = []
        cpu_data[ip].append(p)

    random.seed(0)
    pool = Pool(processes=args.nproc)
    dm = pool.map(calc_dmat,sorted(list(cpu_data.values())))
    pool.close()

    dm = sp.array(dm)
    wdm =dm[:,0].sum(axis=0)
    npairs=dm[:,2].sum(axis=0)
    npairs_used=dm[:,3].sum(axis=0)
    dm=dm[:,1].sum(axis=0)

    w = wdm>0
    dm[w]/=wdm[w,None]


    out = fitsio.FITS(args.out,'rw',clobber=True)
    head = {}
    head['REJ']=args.rej
    head['RPMAX']=cf.rp_max
    head['RTMAX']=cf.rt_max
    head['NT']=cf.nt
    head['NP']=cf.np
    head['NPROR']=npairs
    head['NPUSED']=npairs_used

    out.write([wdm,dm],names=['WDM','DM'],header=head)
    out.close()

    
