"""Contains code to calculate Bayesian posterior distributions for 
parameters calculated using estimate_magnitude.py

Jonathan Griffin
Geoscience Australia 
July 2018
"""

import sys, os
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Polygon
from mpl_toolkits.axes_grid1 import make_axes_locatable
import ogr
from osgeo import osr
from shapely.wkt import loads
from shapely.geometry import LineString, mapping
from scipy import interpolate
from scipy.stats import norm
from adjustText import adjust_text # Small package to improve label locations                                                         
from collections import OrderedDict                     
import fiona

megathrust=False # Flag for plotting special cases
slab=False
plot_additions = None # Variable for storing additional info to be added to plots
event_name = ''


#gmpe_weights = [0.5, 0.5]
#data_files = ['outputs/1918Qld_SomervilleEtAl2009NonCratonic_parameter_llh.csv']
output_filepath = '/g/data/n74/magpie/2015_eidsvold'
input_filepath = '../Australia-Magnitudes-Historical/events/2015_eidsvold/'
filenames = ['2015_eidsvold_Allen2012_SS14_parameter_llh.csv']
gmpe_weights = [1.0]
data_files = []
for filename in filenames:
    data_files.append(os.path.join(output_filepath, filename))

#mmi_obs_file = 'data/1918Qld.txt'
mmi_obs_file = '../Australia-Magnitudes-Historical/events/2015_eidsvold/2015_eidsvold.txt'                    
num_params=6
special_bvalue = 1.237

#data_files = ['outputs/1699megathrust_AtkinsonBoore2003SInter_parameter_llh.csv']#,
#              'outputs/1699megathrust_ZhaoEtAl2006SInter_parameter_llh.csv',
#              'outputs/1699megathrust_AbrahamsonEtAl2015SInter_parameter_llh.csv']
#gmpe_weights = [1.0]#[0.2, 0.3, 0.5]
#mmi_obs_file = 'data/1699HMMI_weighted_mod.txt'
#num_params = 4 # reduce by 3 as strike, dip and depth dependent on location on plane
#data_files = ['outputs/1840_CampbellBozorgnia2014_parameter_llh.csv',
#              'outputs/1840_BooreEtAl2014_parameter_llh.csv',
#              'outputs/1840_ChiouYoungs2014_parameter_llh.csv']
#gmpe_weights = [0.15, 0.5, 0.35]
#mmi_obs_file = 'data/1840HMMI.txt'
#num_params = 7
#data_files = ['outputs/1847_BooreEtAl2014_parameter_llh.csv',
#              'outputs/1847_ChiouYoungs2014_parameter_llh.csv',
#              'outputs/1847_CampbellBozorgnia2014_parameter_llh.csv']
#gmpe_weights = [0.5, 0.35, 0.15]
#mmi_obs_file = 'data/1847HMMI.txt'
#num_params=7
#data_files = ['outputs/1867_BooreEtAl2014_parameter_llh.csv',                                
#              'outputs/1867_ChiouYoungs2014_parameter_llh.csv',                                                          
#              'outputs/1867_CampbellBozorgnia2014_parameter_llh.csv']                                                        
#gmpe_weights = [0.5, 0.35, 0.15]                                                                                                 

#plot_additions = {'mag': 6.5, # USGS data
#                  'longitude': 108.174,
#                  'latitude': -7.492,
#                  'depth': 90.0}


mag_prior_type = 'GR' #'GR' #'uniform'
set_sigma=True

bbox_dict = {#1699: '104/110/-10.5/-5',
             #1780: '104/113/-9/-5',
             #1834: '105/110/-8/-5',
             #1840: '108.0/114/-9/-5',
             #1847: '105/110/-9/-5',
             #1867: '105.7/116/-12/-3',
             #1815: '112/120/-10/-5',
             #1818: '112/121/-10/-5',
             #1820: '113/124/-10/-4',
             #2006: '108.0/114/-9/-5',
             #2017: '104/114/-10.5/-5',
             #2018: '112/118/-10/-5',
             #1852: '126/134/-8.5/0',
             #1896: '96/109/-7.5/0',
             1918: '146/154/-30/-21'}

print('sum(gmpe_weights)', sum(gmpe_weights))
# Read observation data                                                                                                              
mmi_obs = np.genfromtxt(mmi_obs_file)

#if sum(gmpe_weights) != 1.:
#    msg = 'GMPE weights must sum to 1'
#    raise(msg)

# function fro roman numerals                                                                                                                              
def write_roman(num):

    roman = OrderedDict()
    roman[1000] = "M"
    roman[900] = "CM"
    roman[500] = "D"
    roman[400] = "CD"
    roman[100] = "C"
    roman[90] = "XC"
    roman[50] = "L"
    roman[40] = "XL"
    roman[10] = "X"
    roman[9] = "IX"
    roman[5] = "V"
    roman[4] = "IV"
    roman[1] = "I"

    def roman_num(num):
        for r in list(roman.keys()):
            x, y = divmod(num, r)
            yield roman[r] * x
            num -= (r * x)
            if num > 0:
                roman_num(num)
            else:
                break

    return "".join([a for a in roman_num(num)])

def update_weights_gmpe(parameter_space, prior_pdfs, lonlat_prior_array=False):
    """Update weights in a Bayesian sense                                    
    Include GMPE uncertainty
    """
    prior_weights = []
    llhs = parameter_space[7]
    #print llhs, sum(llhs)
    print(max(llhs), min(llhs))
    parameter_space = parameter_space.T
    for combo in parameter_space:
        i0 = np.where(prior_pdfs[0][0]==combo[0])
        i1 = np.where(prior_pdfs[0][1]==combo[1])
        i2 = np.where(prior_pdfs[0][2]==combo[2])
        i3 = np.where(prior_pdfs[0][3]==combo[3])
        i4 = np.where(prior_pdfs[0][4]==combo[4])
        i5 = np.where(prior_pdfs[0][5]==combo[5])
        i6 = np.where(prior_pdfs[0][6]==combo[8])
        if lonlat_prior_array:
            print('lonlat_prior_array is true')
            intersection = np.intersect1d(i1,i2)
            i1 = intersection[0]
            i2 = i1
        try:
            prior_weight = prior_pdfs[1][0][i0] * prior_pdfs[1][1][i1] * \
                prior_pdfs[1][2][i2] * prior_pdfs[1][3][i3] * \
                prior_pdfs[1][4][i4] * prior_pdfs[1][5][i5] * \
                prior_pdfs[1][6][i6]
#            print 'prior_weight', prior_weight
        except IndexError:
            print(combo)
            print(i0,i1,i2,i3,i4,i5,i6)
            print(len(prior_pdfs[1][0]), len(prior_pdfs[1][1]))
            print(len(prior_pdfs[1][2]), len(prior_pdfs[1][3]))
            print(len(prior_pdfs[1][4]), len(prior_pdfs[1][5]))
            print(len(prior_pdfs[1][6]))
            print((prior_pdfs[1][0]))
            print((prior_pdfs[1][1]))
            print((prior_pdfs[1][2]))
            print((prior_pdfs[1][3]))
            print((prior_pdfs[1][4]))
            print((prior_pdfs[1][5]))
            print((prior_pdfs[1][6]))
            print('Error in indexing of priors, check priors are defined for full parameter space')
            sys.exit()
        prior_weights.append(prior_weight)
    prior_weights = np.array(prior_weights).flatten()
    print(max(prior_weights), min(prior_weights))
    print(max(llhs), min(llhs))
    posterior_probs = llhs*prior_weights/sum(llhs*prior_weights)
    return posterior_probs

def update_weights(parameter_space, prior_pdfs):
    """Update weights in a Bayesian sense
    """
    prior_weights = []
    llhs = parameter_space[7]
    parameter_space = parameter_space.T
    for combo in parameter_space:
        i0 = np.where(prior_pdfs[0][0]==combo[0])
        i1 = np.where(prior_pdfs[0][1]==combo[1])
        i2 = np.where(prior_pdfs[0][2]==combo[2])
        i3 = np.where(prior_pdfs[0][3]==combo[3])
        i4 = np.where(prior_pdfs[0][4]==combo[4])
        i5 = np.where(prior_pdfs[0][5]==combo[5])
        prior_weight = prior_pdfs[1][0][i0] * prior_pdfs[1][1][i1] * \
            prior_pdfs[1][2][i2] * prior_pdfs[1][3][i3] * \
            prior_pdfs[1][4][i4] * prior_pdfs[1][5][i5]

        prior_weights.append(prior_weight)
    prior_weights = np.array(prior_weights).flatten()
    posterior_probs = llhs*prior_weights/sum(llhs*prior_weights)#prior_weights)#denominator
    return posterior_probs

def parameter_pdf(parameter_space, fig_comment='', mmi_obs=None, limits_filename=None,
                  bbox=None, localities_file = None, plot_additions=None):
    """Calculate a pdf for parameter values based on the uncertainty model                                
    """

    xlabel_dict = {'mag': 'Magnitude ($M_w$)', 'longitude': 'Longitude',
                   'latitude': 'Latitude', 'depth': 'Depth (km)',
                   'strike': 'Strike ($^\circ$)', 'dip':'Dip ($^\circ$)'}
    parameter_dict = {'mag': 0, 'longitude': 1,
                      'latitude': 2, 'depth': 3,
                      'strike': 4, 'dip':5}
    parameter_pdf_sums = {}
    parameter_pdf_values = {}
    plt.clf()
    fig = plt.figure(figsize=(16,8))#, tight_layout=True)                                                 
    gs = plt.GridSpec(2,4)
    for key, value in parameter_dict.items():
        if key=='longitude' or key=='latitude':
            continue # Do later
        unique_vals = np.unique(parameter_space[value])
        pdf_sums = []
        bin=False
        # Determine if we need to bin values of strike and dip (i.e.                                      
        # for non-area sources                                                                            
        if key == 'strike':
            if len(unique_vals) > 24:
                bin=True
                if megathrust or slab:
                   bins =  np.arange(0, 360, 5.)
                else:
                    bins =  np.arange(0, 360, 15.)
        if key == 'dip' or key == 'depth':
            if len(unique_vals) > 4:
                bin=True
                if key == 'dip':
                    if (max(parameter_space[value]) - min(parameter_space[value])) > 10.0:
                        bins = np.arange(min(parameter_space[value]), max(parameter_space[value])+5, 5.)
                    else:
                        bins = np.arange(min(parameter_space[value]), max(parameter_space[value])+1, 1.)
                elif key == 'depth':
                    if max(parameter_space[value]) > 80.0:
                        bins = np.arange(min(parameter_space[value]), max(parameter_space[value])+20, 20.)
                    else:
                        bins = np.arange(0.0, max(parameter_space[value])+5.0, 5.)
        if bin: # Calculate as histogram                                                                                                           
            hist, bins = np.histogram(parameter_space[value], bins)
            # align to bin centre for plotting                                                                                                     
                #bin_width = bins[1] - bins[0]                                                                                                         
            unique_vals = []
            for i, edge in enumerate(bins):
                try:
                    ind = np.intersect1d(np.where(parameter_space[value] >= edge),
                                         np.where(parameter_space[value] < bins[i+1]))
                except IndexError:
                    ind = np.where(parameter_space[value] >= edge)[0] #[0] to get array from tuple
                pdf_sum = 0
                for index in ind:
#                    likelihood = np.power((1/(self.sigma*np.sqrt(2*np.pi))), len(self.mmi_obs)) * \
#                        np.exp((-1/2)*((self.sum_squares_list[index]/self.sigma**2)))
                    posterior_prob = parameter_space[7][index]
                    pdf_sum += posterior_prob
                    #pdf_sum = np.sum(self.uncert_fun.pdf(self.rmse[ind]))                                                                             
                pdf_sums.append(pdf_sum)
                unique_vals.append(edge)# + bin_width)      
        else: # Use raw values                                                                                                                     
            for val in unique_vals:
                # Just unique values, as pdf sums are repeated                                                                                     
                ind = np.argwhere(parameter_space[value]==val)
                pdf_sum = 0
                for index in ind:
#                    likelihood = np.power((1/(self.sigma*np.sqrt(2*np.pi))), len(self.mmi_obs)) * \
#                        np.exp((-1/2)*((self.sum_squares_list[index]/self.sigma**2)))
                    posterior_prob = parameter_space[7][index]
                    pdf_sum += posterior_prob
                    #pdf_sum = np.sum(self.uncert_fun.pdf(self.rmse[ind]))                                                                             
                pdf_sums.append(pdf_sum)
        pdf_sums = np.array(pdf_sums)
        parameter_pdf_sums[key] = pdf_sums
        parameter_pdf_values[key] = unique_vals

        # Get the best-fit value for plotting on top                                                                                              
        index = np.argmin(parameter_space[6])
        best_fit_x =  parameter_space[value][index]
        index_posterior = np.argmax(parameter_space[7])
        best_fit_x_posterior = parameter_space[value][index_posterior]
        #y_index = np.where(unique_vals == best_fit_x)[0]                                                                                          
        try:
            y_index = (np.abs(unique_vals - best_fit_x)).argmin()[0]
        except IndexError:
            y_index = (np.abs(unique_vals - best_fit_x)).argmin()
        best_fit_y = pdf_sums[y_index]
        try:
            y_index_posterior = (np.abs(unique_vals - best_fit_x_posterior)).argmin()[0]
        except IndexError:
            y_index_posterior = (np.abs(unique_vals - best_fit_x_posterior)).argmin()
        best_fit_y_posterior = pdf_sums[y_index_posterior]

        # Now calculate the range that contains 95% of the distribution
        # Sort the pdf values, descending
        pdf_sums_flat = pdf_sums.flatten()
        try:
            unique_vals_flat = unique_vals.flatten()
        except AttributeError:
            unique_vals_flat = np.array(unique_vals).flatten()
        sorted_probs_args = np.argsort(pdf_sums_flat)[::-1]#.argsort()
        sorted_probs = pdf_sums_flat[sorted_probs_args]
        sorted_values = unique_vals_flat[sorted_probs_args]
        sum_probs = sum(sorted_probs)
        prob_limit = 0.95*sum_probs
        print('Sum probs, should be 1', sum_probs)
        print(prob_limit)
        prob_sum = 0.0
        for pi, prob_val in enumerate(sorted_probs):
            if prob_sum > prob_limit:
                prob_index = pi
                break
            else:
                prob_sum += prob_val
        values_in_bounds = sorted_values[0:prob_index]
        min_bound = min(values_in_bounds)
        max_bound = max(values_in_bounds)
        print('min_bound', min_bound)
        print('max_bound', max_bound)

        # Get plot additions to plot on top
#        if plot_additions is not None:
#            x_addition = plot_additions[key]
#            try:
#                y_index = np.where(unique_(np.abs(unique_vals - best_fit_x)).argmin()[0]
#            except IndexError:
#                y_index = (np.abs(unique_vals - best_fit_x)).argmin()
#            best_fit_y = pdf_sums[y_index]

        # Now plot the results
        print('unique_vals', unique_vals)
        print('unique_vals[1]', unique_vals[1])
        try:
            width = unique_vals[1] - unique_vals[0] # Scale width by discretisation                                                                
        except IndexError: # if only one value                                                                                                     
            width = 1.0
        print('width', width, type(width))
        print('np.deg2rad(unique_vals)', np.deg2rad(unique_vals))
        print('pdf_sums.shape', pdf_sums.shape)
        pdf_sums = pdf_sums.flatten()
        print('pdf_sums.shape', pdf_sums.shape)
        if key=='strike':
            # Plot as rose diagram                                                                                                                 
            ax = fig.add_subplot(gs[0,3],projection='polar')
            ax.bar(np.deg2rad(unique_vals), pdf_sums, width=np.deg2rad(width), bottom=0.0,
                   align='center', color='0.5', edgecolor='k', linewidth=0.5)
            ax.scatter(np.deg2rad(best_fit_x), best_fit_y, marker = '*', c='#696969', edgecolor='k', s=100,zorder=10 )
            ax.scatter(np.deg2rad(best_fit_x_posterior), best_fit_y_posterior, marker = '*', c='w', edgecolor='k', s=500,zorder=9 )
            ax.set_theta_zero_location('N')
            ax.set_theta_direction(-1)
            ax.set_thetagrids(np.arange(0, 360, 15))
            # Define grids intervals for radial axis                                                                                               
            if max(pdf_sums) < 0.21:
                r_int = 0.02
            else:
                r_int = 0.2
            ax.set_rgrids(np.arange(r_int, max(pdf_sums)+0.01, r_int), angle= np.deg2rad(7.5))#, weight= 'black')
            ax.set_xlabel(xlabel_dict[key])
            ax.text(-0.07, 1.02, 'c)', transform=ax.transAxes, fontsize=14)
        elif key == 'mag':
            ax =  fig.add_subplot(gs[0,2])
            ymax = max(pdf_sums)*1.1
#            lbx = [self.min_mag, self.min_mag]
#            lby = [0, ymax]
#            ubx = [self.max_mag, self.max_mag]
#            uby = [0, ymax]
        elif key == 'depth':
            ax =  fig.add_subplot(gs[1,3])
            ymax = max(pdf_sums)*1.1
#            lbx = [self.min_depth, self.min_depth]
#            lby = [0, ymax]
#            ubx = [self.max_depth, self.max_depth]
#            uby = [0, ymax]
        elif key == 'dip':
            ax =  fig.add_subplot(gs[1,2])
            ymax = max(pdf_sums)*1.1
#            lbx = [self.min_dip, self.min_dip]
#            lby = [0, ymax]
#            ubx = [self.max_dip, self.max_dip]
#            uby = [0, ymax]
        print('width', width, type(width))
        print('unique_vals', unique_vals)
        pdf_sums = pdf_sums.flatten()
        print('pdf_sums', pdf_sums)
        if key == 'mag' or key == 'dip' or key == 'depth' :
            ax.bar(unique_vals, pdf_sums, width, align='center', color='0.5')
            ax.scatter(best_fit_x, best_fit_y, marker = '*', c='#696969',
                       edgecolor='k', s=100, zorder=11)
            ax.scatter(best_fit_x_posterior, best_fit_y_posterior, marker = '*', c='w',
                       edgecolor='k', s=500, zorder=9)
            if min_bound != max_bound:
                ax.plot([min_bound, min_bound], [0.0, ymax], linewidth=0.9, linestyle='--', c='k')
                ax.plot([max_bound,max_bound], [0.0, ymax], linewidth=0.9, linestyle='--', c='k')
            if plot_additions is not None:
                try:
                    x_addition = plot_additions[key]
                    y_addition = best_fit_y_posterior*1.03
                except KeyError:
                    x_addition = None
                if x_addition is not None:
                    ax.scatter(x_addition, y_addition, marker = '*', c='b',
                       edgecolor='k', s=200, zorder=10)
                
            ax.set_ylim(0, ymax)
            ax.set_ylabel('Probability')
            ax.set_xlabel(xlabel_dict[key])
            if key == 'mag':
                ax.text(-0.07, 1.02, 'b)', transform=ax.transAxes, fontsize=14)
                ax.set_xlim((min(unique_vals)-0.4), (max(unique_vals)+0.2))
            if key == 'dip':
                ax.text(-0.07, 1.02, 'd)', transform=ax.transAxes, fontsize=14)
            if key == 'depth':
                ax.text(-0.07, 1.02, 'e)', transform=ax.transAxes, fontsize=14)
    # Now plot a map of location uncertainty                                                                                                       
    # First get 2D pdf                                                                                                                             
    pdf_sums = []
    all_lons = []
    all_lats = []
    lon_lat_pairs = []
    for ll,la in zip(parameter_space[parameter_dict['longitude']], 
                     parameter_space[parameter_dict['latitude']]):
        if [ll, la] not in lon_lat_pairs:
            lon_lat_pairs.append([ll, la])
    for lon_lat_pair in lon_lat_pairs:
        index = np.intersect1d(np.argwhere(parameter_space[parameter_dict['longitude']]==lon_lat_pair[0]), \
                                   np.argwhere(parameter_space[parameter_dict['latitude']]==lon_lat_pair[1]))
        pdf_sum = np.sum(parameter_space[7][index])#uncert_fun.pdf(rmse[index]))                                                       
        pdf_sums.append(pdf_sum)
        all_lons.append(lon_lat_pair[0])
        all_lats.append(lon_lat_pair[1])
    # Normalise pdf sums                                                                                                                   
        
    pdf_sums = np.array(pdf_sums)
    parameter_pdf_sums['lon_lat'] = pdf_sums
    all_lons = np.array(all_lons)
    all_lats = np.array(all_lats)
    # Dump data for testing
    data_dump = np.vstack((all_lons, all_lats, pdf_sums)).T
    np.savetxt('data_dump.csv', data_dump, delimiter=',', header='lon,lat,pdf_sum')
    # Get best fit value                                                                                                 
    index = np.argmin(parameter_space[6])
    best_fit_lon =  parameter_space[parameter_dict['longitude']][index]
    best_fit_lat =  parameter_space[parameter_dict['latitude']][index]
    index_posterior = np.argmax(parameter_space[7])
    best_fit_lon_posterior =  parameter_space[parameter_dict['longitude']][index_posterior]
    best_fit_lat_posterior =  parameter_space[parameter_dict['latitude']][index_posterior]
    proj=ccrs.PlateCarree()
    ax =  fig.add_subplot(gs[:,0:2], projection=proj)
#    bbox = bbox.split('/')
    if bbox is not None:
        bbox = bbox.split('/')
        minlon = float(bbox[0])
        maxlon = float(bbox[1])
        minlat = float(bbox[2])
        maxlat = float(bbox[3])
    else:
        minlon = min(parameter_space[parameter_dict['longitude']])#parameter_pdf_values['longitude'])
        maxlon = max(parameter_space[parameter_dict['longitude']])#parameter_pdf_values['longitude'])
        minlat = min(parameter_space[parameter_dict['latitude']])#parameter_pdf_values['latitude'])
        maxlat = max(parameter_space[parameter_dict['latitude']])#parameter_pdf_values['latitude'])
    lat_0 = minlat + (maxlat-minlat)/2.
    lon_0 = minlon + (maxlon-minlon)/2.

    ax.coastlines(linewidth=0.5,color='k')
    ax.add_feature(cf.BORDERS, color='0.2')
    print('minlon, maxlon, minlat, maxlat')
    print(minlon, maxlon, minlat, maxlat)
    ax.set_extent([minlon, maxlon, minlat, maxlat], crs=proj)
    
    if maxlon-minlon < 2:
        gridspace = 0.5
    elif maxlon-minlon < 3:
        gridspace = 1.0
    elif maxlon-minlon < 7:
        gridspace = 2.0
    else:
        gridspace = 5.0
    # Add some gridlines    
    gl = ax.gridlines(draw_labels=True, crs=proj)
    gl.xlabels_top = False
    gl.ylabels_right = False

    max_val = max(pdf_sums)*1.1
    clevs = np.arange(0.0,max_val,(max_val/50))
    cmap = plt.get_cmap('gray_r')
    # Adjust resolution to avoid memory intense interpolations                                                       
    res = max((maxlon-minlon)/50., (maxlat-minlat)/50.) #75 #30 #50
    xy = np.mgrid[minlon:maxlon:res,minlat:maxlat:res]
    xx,yy=np.meshgrid(xy[0,:,0], xy[1][0])
    griddata = interpolate.griddata((all_lons, all_lats), pdf_sums, (xx,yy), method='nearest') # nearest # linear
    # now plot filled contours of pdf
    # Get percentiles:
    n = 1000
    griddata_norm = griddata/griddata.sum()
    t = np.linspace(0, griddata_norm.max(), n)
    integral = ((griddata_norm >= t[:, None, None]) * griddata_norm).sum(axis=(1,2))
    f = interpolate.interp1d(integral, t)
    t_contours = f(np.array([0.95, 0.75, 0.5, 0.25]))
    origin = 'lower'
    csp = plt.contour(xx,yy,griddata_norm, levels=t_contours,
                      colors=('k',),
                      linewidths=(1,),
                      origin=origin)
    cs = ax.contourf(xx, yy, griddata, clevs, cmap=cmap, vmax=max_val, vmin=0.0, transform=proj)#latlon=True)
    lines = []
    # Get contours to LineStrings
    for l,c in enumerate(csp.collections):
        c_path = c.get_paths()[0]
        verts = c_path.vertices
        line = LineString([(j[0], j[1]) for j in zip(verts[:,0], verts[:,1])])
        lines.append(line)
    # Write to shapefile
    shapefile_name = '%s_location_contours.shp' % fig_comment
    schema = {'geometry': 'LineString','properties': {'id': 'int'}}  # sets up parameter for shapefile
    with fiona.open(shapefile_name, 'w', 'ESRI Shapefile', schema) as c:  # creates new file to be written to
        for j in range(len(lines)):
            l = (lines[j])   # creates variable
            c.write({'geometry': mapping(l),'properties': {'id': j},})   
    print('Contours plotted')

    #Dump data to file
#    loc_data = np.array(xx,yy,griddata)
#    np.savetxt(loc_data, 
    # Mask areas outside of source model                                                                                
    if limits_filename is not None:
        limits_data = np.genfromtxt(limits_filename, delimiter=',')
        limits_x = limits_data[:,0]
        limits_y = limits_data[:,1]
#        limits_x, limits_y = ax.transAxes.transform(limits_x, limits_y)
##        limits_x, limits_y = m(limits_x, limits_y) # Convert to map coordinates                                     
        poly = Polygon(np.c_[limits_x, limits_y], closed=True)
        clippath =  poly.get_path()
        patch = PathPatch(clippath, transform=ax.transData, facecolor='none', linewidth=0.4, linestyle='--')
        print('Adding patch')
        ax.add_patch(patch)
        for contour in cs.collections:
            contour.set_clip_path(patch)
        print('Patch added')
    #plt.tight_layout()
    # Now add some locations
    print('Add some locations here')
    if localities_file is not None:
        f_in = open(localities_file)
        loc_lon = []
        loc_lat = []
        loc_name = []
        for line in f_in.readlines():
            row = line.split()
            loc_lon.append(float(row[0]))
            loc_lat.append(float(row[1]))
            loc_name.append(row[2])
        print('loc_lon', loc_lon, type(loc_lon))
        print('loc_lat', loc_lat)
        loc_sp = ax.scatter(loc_lon, loc_lat, c='k', s=40, marker='s', transform=proj)#proj=projection)#latlon=True)
        texts = []
        for label, x, y in zip(loc_name, loc_lon, loc_lat):
            #x,y =  m(x,y)
            texts.append(plt.text(x,y,label, transform=proj, fontsize=14, color='0.4', zorder=20))

    # Now add historical points on top
    print('Adding historical points to plot')
    if mmi_obs is not None:
        clevs = np.arange(0.5,9.5,1.0)
        cmap = plt.get_cmap('YlOrRd', 7)
        mmi_labels = []
        for obs in mmi_obs[:,2]:
            mmi_labels.append(write_roman(int(obs)))
        print('mmi_obs[:,0]', mmi_obs[:,0], type(mmi_obs[:,0]))
        print('mmi_obs[:,1]', mmi_obs[:,1])
        sp = ax.scatter(mmi_obs[:,0], mmi_obs[:,1], c=mmi_obs[:,2], cmap=cmap,
                        vmin=1.5, vmax=8.5, s=30, transform=ccrs.Geodetic())# latlon=True)
        sp_ticks = np.arange(1,9,1)
        # Label only if there aren't too many to avoid plots being too busy
        print('plotted')
        if len(mmi_obs[:,2]) < 20:
            for label, x, y in zip(mmi_labels, mmi_obs[:,0], mmi_obs[:,1]):
                texts.append(plt.text(x,y,label, fontsize=10, transform=proj))
        if len(texts) > 0:
            print('Adjusting texts')
            print(texts)
            adjust_text(texts, only_move = {"text": "xy"},
                        arrowprops=dict(arrowstyle="-",
                                        color='k', lw=0.5))
        print('set colour bar')
        cbar1 = fig.colorbar(sp, ticks=sp_ticks, location='right', pad = 0.2)
        cbar1.ax.set_ylabel('MMI')

    # Now add best-fit location on top
    print('Adding best-fit location')
    ax.scatter(best_fit_lon, best_fit_lat, marker = '*', facecolor='none', #c='#696969',
              edgecolor='k', s=100, zorder=10, transform=proj)#latlon=True)
    ax.scatter(best_fit_lon_posterior, best_fit_lat_posterior, marker = '*', facecolor='none',
               edgecolor='k', s=500, zorder=9, transform=proj)
    print('Plot additions')
    if plot_additions is not None:
        try:
            x_addition = plot_additions['longitude']
            y_addition = plot_additions['latitude']
        except KeyError:
            x_addition = None
        if x_addition is not None:
            ax.scatter(x_addition, y_addition, marker = '*', c='b',
                       edgecolor='k', s=200, zorder=10, transform=proj)#latlon=True)
    print('Add annotation')
    plt.annotate('a)', xy=(-0.01, 1.01),xycoords='axes fraction', fontsize=14)
    if max_val < 0.0000001:
        loc_int = 0.00000001
    elif max_val < 0.000001:
        loc_int = 0.0000001
    elif max_val < 0.00001:
        loc_int = 0.000001
    elif max_val < 0.0001:
        loc_int = 0.00001
    elif max_val < 0.001:
        loc_int = 0.0001
    elif max_val < 0.01:
        loc_int = 0.001
    elif max_val < 0.1:
        loc_int = 0.01
    else:
        loc_int = 0.1
    ticks = np.arange(0.0, max_val*1.1, loc_int)
    print('Add another colour bar')
    cbar = fig.colorbar(cs, ticks=ticks, location='bottom')#orientation='horizontal')
    cbar.ax.set_xlabel('Probability')
    figname = '%s_all_parameter_pdf.png' % (fig_comment)
    figname = figname.replace('()', '')
    print('Call tight_layout')
    plt.tight_layout()
    print('Saving figure')
    plt.savefig(figname, dpi=600, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
#    plt.savefig(figname, dpi=600, format='pdf', bbox_inches='tight')
    

def gaussian_location_prior(shapefile, sigma, lons, lats):
    """Based on the location in shapefile and sigma, a Gaussian
    prior distribution is applied such that points located closest
    to the shapefile edge are given the highest weight
    :param shapefile: polygon where point closest to the edge have
    the highest weight.
    :param sigma: standard deviation of the gaussian distirbution (in geographic
    coordinates)
    :param lons: array of longitudes for search points
    :param lats: array of latitudes for search points

    returns
    :lon_priors: prior distribution of longitudes
    :lat_priors: prior distribution of latitudes
    """

    # Load coastline polygon shapefile
    file = ogr.Open(shapefile, 1)
    layer = file.GetLayer()

    # Create point geometry
    pts = []
    for i, lon in enumerate(lons):
#        for lat in lats:
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.AddPoint(lon, lats[i])
        pts.append(pt)

    polygon = layer.GetFeature(0)#.GetGeometryRef()

    # Reproject point to shapefile's srs
    geo_ref = layer.GetSpatialRef()
    pt_geo_ref = osr.SpatialReference()
    pt_geo_ref.ImportFromEPSG(4326)#

    trans_pts = []
    transform = osr.CoordinateTransformation(pt_geo_ref, geo_ref)
    for pt in pts:
        pt.Transform(transform)
        trans_pts.append(pt)
    # Assume both in WGS84 for now
    shapely_poly = loads(polygon.GetGeometryRef().ExportToWkt())
    dist = polygon.GetGeometryRef().Distance(pt)

    distances = []
    # Check for intersection and distance from the closest edge
    for pt in trans_pts:
        if pt.Intersection(polygon.GetGeometryRef()).ExportToWkt() == 'GEOMETRYCOLLECTION EMPTY':
            # outside polygon
            dist = polygon.GetGeometryRef().Distance(pt)
            distances.append(dist)
        else:
            # within polygon
            shapely_pt = loads(pt.ExportToWkt())
            dist = shapely_poly.exterior.distance(shapely_pt)
            distances.append(dist)
    # calculate prior probabilities based on distance from shapefile boundary
    prior_probs = norm(0, sigma).pdf(distances)
    prior_probs_normalised = prior_probs/sum(prior_probs)

    
    return prior_probs_normalised

if __name__ == "__main__":
    if not os.path.exists('figures'):
        os.makedirs('figures')

    # Combine for different GMPEs
    year = data_files[0].split('/')[-1][:4]
    year = int(year)
    print('year', year)
    if event_name == '1852Banda_area' or event_name == '1852BandaDetachment' \
            or event_name == '1852Banda_doughnut' or event_name =='1852Banda_domain_ryan_mmi'\
            or event_name == '1852Banda_domain_FH_mmi' or event_name =='1852Banda_exclude_20min_ryan_mmi'\
            or event_name =='1852Banda_exclude_20min_FH_mmi' or event_name =='1852Banda_exclude_15min_ryan_mmi'\
            or event_name =='1852Banda_exclude_15min_FH_mmi':
        pass
    else:
        event_name = data_files[0].split('/')[-1].split('_')[0] + '_' + data_files[0].split('/')[-1].split('_')[1]
    fig_folder = output_filepath + '/figures/'
    if not os.path.exists(fig_folder):
        os.makedirs(fig_folder)           
    fig_comment = fig_folder + event_name + '_all_gmpes_mag_pr_' + mag_prior_type
    # Get limits_filename from params.txt
    param_filename = os.path.join(input_filepath, (event_name + '_params.txt'))
    f_in = open(param_filename)
    limits_filename = None
    for line in f_in.readlines():
        row = line.rstrip().split(',')
        if row[0] == 'limits_filename':
            limits_filename = row[1]
    gmpe_inds = []
    # Count number of data points
#    event = data_files[0].split('/')[1][:4]    
    #hmmi_file  = 'data/' + event + 'HMMI.txt'
    with open(mmi_obs_file) as f:                                                                                       
        for obs_count, l in enumerate(f):                                                      
            pass                                                                                                         
    num_obs = obs_count + 1                                                                              
    print('num_obs', num_obs) 
    # Here we add a dimension to the parameter space that contains an index
    # for which gmpe was used
    for i, filename in enumerate(data_files):
        gmpe_inds.append(i)
        if i == 0:
            parameter_space = np.genfromtxt(filename, delimiter=',', skip_header=1, invalid_raise=False)
            parameter_space = parameter_space.T
            gmm_ids = np.array([np.ones(len(parameter_space[7]))*i])
#            print parameter_space
#            print gmm_ids
            parameter_space = np.concatenate([parameter_space, gmm_ids])
            parameter_space = parameter_space.T
        else:
            tmp_ps = np.genfromtxt(filename, delimiter=',', skip_header=1, invalid_raise=False)
            tmp_ps = tmp_ps.T
            gmm_ids = np.array([np.ones(len(tmp_ps[7]))*i])
            tmp_ps = np.concatenate([tmp_ps, gmm_ids])
            tmp_ps = tmp_ps.T
            parameter_space = np.concatenate([parameter_space, tmp_ps])
    parameter_space = parameter_space.T
    # Set up prior pdfs - set-up using basic assumptions and limits of data
    # magnitude - based on Gutenberg-Richter assuming b value = 1, and that
    # CDF from mmin to mmax = 1                                                                                         
    mags = np.unique(parameter_space[0])
    # Hack to avoid help get intcremental rate on max mag by adding a bin
    mags = list(mags)
    mags.append(max(mags)+0.1)
    mags = np.array(mags)
    mmax = max(mags)
    mmin = min(mags)
    if special_bvalue in globals():
        b = special_bvalue
        print('Using b-value of %.3f' % b)
    else:
        b=1.0
    a = np.log10(1./(np.power(10,-1*b*mmin) - np.power(10, -1*b*mmax)))
    # Now we need to generate an incremental pdf                                                                                    
    reversed_mag_priors = []
    reversed_mags = list(reversed(mags))
    for i, mag in enumerate(reversed_mags):
        if i == 0:
            prior = np.power(10, a - b*mag)
            # We don't add first bin as this is a dummy bin only
        else:
            prior = np.power(10, a - b*mag) - np.power(10, a - b*reversed_mags[i-1])
            reversed_mag_priors.append(prior)
    mag_priors = np.array(list(reversed(reversed_mag_priors)))

    if mag_prior_type=='uniform':
        mag_priors = np.ones(len(np.unique(parameter_space[0]))) * \
            (1./len(np.unique(parameter_space[0])))
    print('mags',mags)
    print('mag_priors', mag_priors, sum(mag_priors))
        # longitude, latitude, strike, depth and dip - uniform across parameter space                             
    lon_priors = np.ones(len(np.unique(parameter_space[1]))) * \
        (1./len(np.unique(parameter_space[1])))
    lat_priors = np.ones(len(np.unique(parameter_space[2]))) * \
        (1./len(np.unique(parameter_space[2])))
    depth_priors = np.ones(len(np.unique(parameter_space[3]))) * \
        (1./len(np.unique(parameter_space[3])))
    strike_priors = np.ones(len(np.unique(parameter_space[4]))) * \
        (1./len(np.unique(parameter_space[4])))
    dip_priors = np.ones(len(np.unique(parameter_space[5]))) * \
        (1./len(np.unique(parameter_space[5])))

    # Special cases of priors to limit extent of subduction zone megathrust
    # or slab considered
    lonlat_prior_array=False
    if event_name == '1867slab':
        lon_index = np.intersect1d((np.where(np.unique(parameter_space[1]) > 108.0)),
                                   (np.where(np.unique(parameter_space[1]) < 113.0)))
        lon_priors = np.zeros(len(np.unique(parameter_space[1])))
        lon_priors[lon_index] = 1./len(lon_index)
#        print 'Updated longitude priors', lon_priors
##    if event_name == '1852BandaDetachment' or event_name == '1852Banda_area':# \
##           # or event_name == '1852Banda_doughnut':
##        lonlat_priors = gaussian_location_prior('data/ETA_buffer_15min_midline.shp', 0.25, 
 ##                               parameter_space[1], parameter_space[2]) 
                                #np.unique(parameter_space[1]),
                                 #np.unique(parameter_space[2]))
##        lonlat_prior_array=True # lat, lons pts already in pairs
    if lonlat_prior_array:
        print('lonlat_prior_array is True')
        priors = np.array([[np.unique(parameter_space[0]), parameter_space[1],
                            parameter_space[2], np.unique(parameter_space[3]),
                            np.unique(parameter_space[4]), np.unique(parameter_space[5]),
                            gmpe_inds],
                           [mag_priors, lonlat_priors, lonlat_priors,
                            depth_priors, strike_priors, dip_priors,
                            np.array(gmpe_weights)]])
    else:
        print('lonlat_prior_array is False')
        priors = np.array([[np.unique(parameter_space[0]), np.unique(parameter_space[1]),
                            np.unique(parameter_space[2]), np.unique(parameter_space[3]),
                            np.unique(parameter_space[4]), np.unique(parameter_space[5]),
                            gmpe_inds],
                           [mag_priors, lon_priors, lat_priors,
                            depth_priors, strike_priors, dip_priors,
                            np.array(gmpe_weights)]])

        # Re-calculate sigma and then the likelihoods                                                                                               
    min_rmse = min(parameter_space[6])
    print('min_rmse', min_rmse)
    sum_squares = parameter_space[6]**2 # Weighted sum of square*num_obs
    if num_obs > num_params:
        sigma=np.sqrt((1./(num_obs-num_params))*(min_rmse**2))
    else:
        sigma = 0.5 # Estimate sigma based on other results if not enough data
    print('sigma', sigma)
    if set_sigma == True:
        sigma = 0.2
    print('sigma', sigma)
    print(sum_squares, num_obs)
    print(sum_squares/sigma**2)
    likelihoods = np.power((1/(sigma*np.sqrt(2*np.pi))), num_obs) * \
                np.exp((-1/2)*(sum_squares/sigma**2))
    print(min(likelihoods), max(likelihoods))
    print(min(parameter_space[7]), max(parameter_space[7]))
    parameter_space[7] = likelihoods
    # dump likelihoods
    out_array =np.vstack((parameter_space[1],parameter_space[2],parameter_space[7]))
    np.savetxt('test_latlon_likelihoods.csv', out_array.T, delimiter=',', header='lon,lat,likelihoods')
    posterior_probs = update_weights_gmpe(parameter_space, priors,
                                          lonlat_prior_array)
    parameter_space[7] = posterior_probs
    # Write posterior best-fit to file
    posterior_filename = fig_comment + '_best_posterior.txt'
    f_out = open(posterior_filename, 'w')
    header = '#mag,lon,lat,depth,strike,dip,rmse,posterior_prob,gmpe,sigma\n'
    f_out.write(header)
    j = np.argmax(parameter_space[7])
    line = ''
    for k in range(8):
        s = '%.6f,' % parameter_space[k][j]
        line+=s
    s = '%.3f' % sigma
    line+=s
    f_out.write(line)
    f_out.close()
    # Dump some results for spatial location
    out_array =np.vstack((parameter_space[1],parameter_space[2],parameter_space[7]))
    np.savetxt('test_latlon_posterior_probs.csv', out_array.T, delimiter=',', header='lon,lat,posterior_prob')
    try:
        bbox = bbox_dict[year]
    except KeyError:
        bbox = None
    localities_file = 'data/localities%s.txt' % year 
    parameter_pdf(parameter_space, fig_comment = fig_comment, mmi_obs = mmi_obs,
                  limits_filename = limits_filename, bbox=bbox, localities_file = localities_file,
                  plot_additions=plot_additions)
