#PBS -P n74
#PBS -q normal
#PBS -l walltime=48:00:00
#PBS -l ncpus=64
#PBS -l mem=128GB
#PBS -l wd

#module load intel-cc/12.1.9.293
#module load intel-fc/12.1.9.293
#module load gdal
#module load geos/3.5.0
#module load hdf5/1.8.10
#module load openmpi/1.6.3
#module unload python
#module load python/2.7.11
#module load python/2.7.11-matplotlib

# To get rtree to run
#export SPATIALINDEX_C_LIBRARY=/short/n74/jdg547/spatialindex-src-1.8.5/lib/libspatialindex_c.so.4
#export LD_LIBRARY_PATH=/short/n74/jdg547/spatialindex-src-1.8.5/lib:$LD_LIBRARY_PATH
## Python paths for local openquake installs and dependencies
#export PYTHONPATH=.:/short/n74/src/lib/python:${PYTHONPATH}
#export PYTHONPATH=.:/home/547/jdg547/.local/lib/python2.7/site-packages:${PYTHONPATH}
#export PYTHONPATH=.:/short/w84/NSHA18/sandpit/jdg547/oq-hazardlib:${PYTHONPATH}
#export PYTHONPATH=.:/short/w84/NSHA18/sandpit/jdg547/oq-engine:${PYTHONPATH}

module load geos/3.8.0
module load hdf5/1.10.7
module load openmpi/4.1.4
module load python3/3.9.2
# Load gdal after python to avoid conflict                                                                                
module load gdal/3.5.0

# Local pythonpaths                                                                                                        
export PYTHONPATH=.:/home/547/jdg547/.local/lib/python3.9/site-packages:${PYTHONPATH}
export PYTHONPATH=.::/home/547/jdg547/:${PYTHONPATH}
export PYTHONPATH=.::/home/547/jdg547/modelling/oq-engine/:${PYTHONPATH}
export PYTHONPATH=.::/scratch/w84/jdg547/:${PYTHONPATH}

mpirun -np 32 -x PYTHONPATH python3 build_site_col.py >& build_site_col.log
