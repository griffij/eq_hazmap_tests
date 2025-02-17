# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Modifed from openquake prepare_site_model.py
#Jonathan Griffin, Geoscience Australia

import os
import logging
import numpy
from openquake.baselib import performance, writers, hdf5
from openquake.hazardlib import site, valid
from openquake.hazardlib.geo.utils import assoc

from openquake.commonlib import datastore

SQRT2 = 1.414
vs30_dt = numpy.dtype([('lon', float), ('lat', float), ('vs30', float)])


# TODO: equivalents of calculate_z1pt0 and calculate_z2pt5_ngaw2
# are inside some GSIM implementations, we should avoid duplication
def calculate_z1pt0(vs30):
    '''
    Reads an array of vs30 values (in m/s) and
    returns the depth to the 1.0 km/s velocity horizon (in m)
    Ref: Chiou & Youngs (2014) California model
    :param vs30: the shear wave velocity (in m/s) at a depth of 30m
    '''
    c1 = 571 ** 4.
    c2 = 1360.0 ** 4.
    return numpy.exp((-7.15 / 4.0) * numpy.log((vs30 ** 4. + c1) / (c2 + c1)))


def calculate_z2pt5_ngaw2(vs30):
    '''
    Reads an array of vs30 values (in m/s) and
    returns the depth to the 2.5 km/s velocity horizon (in km)
    Ref: Campbell, K.W. & Bozorgnia, Y., 2014.
    'NGA-West2 ground motion model for the average horizontal components of
    PGA, PGV, and 5pct damped linear acceleration response spectra.'
    Earthquake Spectra, 30(3), pp.1087–1114.

    :param vs30: the shear wave velocity (in m/s) at a depth of 30 m
    '''
    c1 = 7.089
    c2 = -1.144
    z2pt5 = numpy.exp(c1 + numpy.log(vs30) * c2)
    return z2pt5


def read(fname):
    if fname.endswith('.gz'):
        return gzip.open(fname, 'rt', encoding='utf-8-sig')
    else:
        print('fname in read', fname)
        return open(fname, 'rt', encoding='utf-8-sig')


def read_vs30(fnames, forbidden):
    """
    :param fnames: a list of CSV files with fields lon,lat,vs30
    :param forbidden: forbidden name for the input files
    :returns: a vs30 array of dtype vs30dt
    """
    data = []
    for fname in fnames:
        check_fname(fname, 'vs30_csv', forbidden)
        with read(fname) as f:
            for line in f:
                if line.startswith('lon,lat'):  # possible header
                    continue
                data.append(tuple(line.split(',')))
    return numpy.array(data, vs30_dt)


def check_fname(fname, kind, forbidden):
    """
    Raise a NameError if fname == forbidden
    """
    if os.path.basename(fname).lower() == forbidden:
        raise NameError('A file of kind %s cannot be called %r!'
                        % (kind, forbidden))


def associate(sitecol, vs30fnames, assoc_distance):
    if vs30fnames[0].endswith('.hdf5'):
        geohashes = numpy.unique(sitecol.geohash(2))
        with hdf5.File(vs30fnames[0]) as f:
            data = []
            for gh in geohashes:
                try:
                    arr = f[gh][:]
                except KeyError:
                    logging.error('Missing data for geohash %s' % gh)
                else:
                    data.append(arr)
            data = numpy.concatenate(data)
            vs30orig = numpy.zeros(len(data), vs30_dt)
            vs30orig['lon'] = data[:, 0]
            vs30orig['lat'] = data[:, 1]
            vs30orig['vs30'] = data[:, 2]
    else:
        vs30orig = read_vs30(vs30fnames, 'site_model.csv')
    logging.info('Associating {:_d} hazard sites to {:_d} site parameters'.
                 format(len(sitecol), len(vs30orig)))
    return sitecol.assoc(vs30orig, assoc_distance,
                         ignore={'z1pt0', 'z2pt5'})


def prep_sites(
        vs30_csv,
        z1pt0=False,
        z2pt5=False,
        vs30measured=False,
        backarc=False,
        *,
        exposure_xml=None,
        sites_csv=[],
        grid_spacing: float = 0,
        assoc_distance: float = 5,
        output='site_model.csv'):
    """
    Prepare a site_model.csv file from exposure xml files/site csv files,
    vs30 csv files and a grid spacing which can be 0 (meaning no grid).
    For each site the closest vs30 parameter is used. The command can also
    generate (on demand) the additional fields z1pt0, z2pt5 and vs30measured
    which may be needed by your hazard model, depending on the required GSIMs.
    """
    hdf5 = datastore.hdf5new()
    req_site_params = {'vs30'}
    fields = ['lon', 'lat', 'vs30']
    if z1pt0:
        req_site_params.add('z1pt0')
    fields.append('z1pt0')
    if z2pt5:
        req_site_params.add('z2pt5')
    fields.append('z2pt5')
#    if vs30measured:
    req_site_params.add('vs30measured')
    fields.append('vs30measured')
    req_site_params.add('backarc')
    fields.append('backarc')    
    with performance.Monitor(measuremem=True) as mon:
        if exposure_xml:
            mesh, assets_by_site = Exposure.read(
                exposure_xml, check_dupl=False).get_mesh_assets_by_site()
            hdf5['assetcol'] = assetcol = site.SiteCollection.from_points(
                mesh.lons, mesh.lats, req_site_params=req_site_params)
            if grid_spacing:
                grid = mesh.get_convex_hull().dilate(
                    grid_spacing).discretize(grid_spacing)
                haz_sitecol = site.SiteCollection.from_points(
                    grid.lons, grid.lats, req_site_params=req_site_params)
                logging.info(
                    'Associating exposure grid with %d locations to %d '
                    'exposure sites', len(haz_sitecol), len(assets_by_site))
                haz_sitecol, assets_by, discarded = assoc(
                    assets_by_site, haz_sitecol,
                    grid_spacing * SQRT2, 'filter')
                if len(discarded):
                    logging.info('Discarded %d sites with assets '
                                 '[use oq plot_assets]', len(discarded))
                    hdf5['discarded'] = numpy.array(discarded)
                haz_sitecol.make_complete()
            else:
                haz_sitecol = assetcol
                discarded = []
        elif len(sites_csv):
            print('sites_csv', sites_csv)
            if hasattr(sites_csv, 'lon'):
                # sites_csv can be a DataFrame when used programmatically
                lons, lats = sites_csv.lon.to_numpy(), sites_csv.lat.to_numpy()
            else:
                # sites_csv is a list of filenames
                lons, lats = [], []
                for fname in sites_csv:
                    check_fname(fname, 'sites_csv', output)
                    with read(fname) as csv:
                        for line in csv:
                            if line.startswith('lon,lat'):  # possible header
                                continue
                            lon, lat = line.split(',')[:2]
                            lons.append(valid.longitude(lon))
                            lats.append(valid.latitude(lat))
            haz_sitecol = site.SiteCollection.from_points(
                lons, lats, req_site_params=req_site_params)
            if grid_spacing:
                grid = haz_sitecol.mesh.get_convex_hull().dilate(
                    grid_spacing).discretize(grid_spacing)
                haz_sitecol = site.SiteCollection.from_points(
                    grid.lons, grid.lats, req_site_params=req_site_params)
        else:
            raise RuntimeError('Missing exposures or missing sites')
        print('vs30_csv', vs30_csv)
        vs30 = associate(haz_sitecol, vs30_csv, assoc_distance)
        if z1pt0:
            haz_sitecol.array['z1pt0'] = calculate_z1pt0(vs30['vs30'])
        if z2pt5:
            haz_sitecol.array['z2pt5'] = calculate_z2pt5_ngaw2(vs30['vs30'])
        if backarc:
            haz_sitecol.array['backarc'] = 1
        else:
            haz_sitecol.array['backarc'] = 0
        if vs30measured:
            haz_sitecol.array['vs30measured'] = 1
        else:
            haz_sitecol.array['vs30measured'] = 0
        hdf5['sitecol'] = haz_sitecol
        if output:
            writers.write_csv(output, haz_sitecol.array[fields])
    logging.info('Saved %d rows in %s' % (len(haz_sitecol), output))
    logging.info(mon)
    return haz_sitecol

def prep_target_sites(target_sites_txt):
    f_in = open(target_sites_txt, 'r')
    lons = []
    lats = []
    for line in f_in.readlines():
        row = line.split()
        lons.append(str(row[0]))
        lats.append(str(row[1]))
    f_in.close()
    target_sites_csv = target_sites_txt.rstrip('txt') + 'csv'
    print(target_sites_csv)
    f_out = open(target_sites_csv, 'w')
    for i in range(len(lons)):
        outline = lons[i] + ',' + lats[i] + '\n'
        f_out.write(outline)
    f_out.close()
    return target_sites_csv
                    
if __name__ == "__main__":
    # First need to prep the target sites
    target_sites_filename = '/home/547/jdg547/modelling/Australia-Magnitudes-Historical/events/1869_gippsland.txt'
    target_sites_csv = prep_target_sites(target_sites_filename)
    output_filename = target_sites_csv.rstrip('.csv').replace('events', 'site_files') + '_prepared.csv'
    print(target_sites_csv)
    prep_sites(['data/asscm_wii_vs30.400.csv'], sites_csv=[target_sites_csv],
               z1pt0=True, z2pt5=True, backarc=False,
               output = output_filename)
    os.remove(target_sites_csv)

