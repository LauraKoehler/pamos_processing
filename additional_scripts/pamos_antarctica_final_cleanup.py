import numpy as np
import xarray as xr
import pandas as pd
import glob

def interpolate_nearest_with_maxgap(da, dim="time", freq="1min", max_gap="1min"):
    """
    Resample to fixed frequency using nearest-neighbor interpolation,
    but only keep values if the nearest neighbor is within max_gap.
    """
    max_gap = np.timedelta64(pd.Timedelta(max_gap))  # ensure ns timedelta
    
    # Resample with nearest
    da_resampled = da.resample({dim: freq}).interpolate("nearest")
    
    # Distance to nearest original observation
    orig_times = da[dim].values
    new_times = da_resampled[dim].values
    
    # For each new time, find distance to nearest original
    idx = np.searchsorted(orig_times, new_times)
    left = np.clip(idx - 1, 0, len(orig_times)-1)
    right = np.clip(idx, 0, len(orig_times)-1)
    
    dist_left = np.abs(new_times - orig_times[left])
    dist_right = np.abs(new_times - orig_times[right])
    nearest_dist = np.minimum(dist_left, dist_right)
    
    # Mask values farther than max_gap
    mask = xr.DataArray(nearest_dist <= max_gap,
                        coords={dim: new_times}, dims=dim)
    return da_resampled.where(mask)

data = xr.open_dataset("20241130_20250326_msfridtjofnansen_pamos.nc")

# Add GPS data from the ship as reference
files = sorted(glob.glob("nansen_gps_old_format/*.nrt"))

for fn in files:
    df = pd.read_csv(fn, delimiter="\t")
    time = df["datetime"].values.astype("datetime64")
    lat = df["lat"].values
    lon = df["lon"].values
    if fn == files[0]:
        times = time
        lats = lat
        lons = lon
    else:
        times = np.append(times, time)
        lats = np.append(lats, lat)
        lons = np.append(lons, lon)

files = sorted(glob.glob("nansen_gps_new_format/*.nrt"))

for fn in files:
    df = pd.read_csv(fn, delimiter="\t")
    time = df["datetime"].values.astype("datetime64")
    lat = df["vessel:soop_fridtjof_nansen:latitude [deg]"].values
    lon = df["vessel:soop_fridtjof_nansen:longitude [deg]"].values
    times = np.append(times, time)
    lats = np.append(lats, lat)
    lons = np.append(lons, lon)

positions = xr.Dataset(coords = {"time": times}, data_vars={"lat": (["time"],lats), "lon": (["time"], lons)})
positions = positions.sortby("time")
lats = interpolate_nearest_with_maxgap(positions.lat, max_gap="1min")
lons = interpolate_nearest_with_maxgap(positions.lon, max_gap="1min")
positions = xr.Dataset(data_vars={"lat": lats, "lon": lons})
positions = positions.sel(time = data.time.values)

# Use air temperature as reliable parameter for running PAMOS
what2keep = np.where(np.isnan(data.t_air.values), np.nan, 1.0)
positions["lat"] = positions.lat * what2keep
positions["lon"] = positions.lon * what2keep

data = data.assign_coords({"lat_ship": (["time"],positions.lat.values), "lon_ship": (["time"],positions.lon.values)})
data["lat_ship"].attrs = {"instrument": "GNSS receiver (MS Fridtjof Nansen)", "long_name": "latitude", "standard_name": "latitude", "units": "degree_north"}
data["lon_ship"].attrs = {"instrument": "GNSS receiver (MS Fridtjof Nansen)", "long_name": "longitude", "standard_name": "longitude", "units": "degree_east"}

data.to_netcdf("20241130_20250326_msfridtjofnansen_pamos_shipposition.nc")

# Export additional csv file for Pangaea
ds = xr.open_dataset("20241130_20250326_msfridtjofnansen_pamos_shipposition.nc")
df = ds.to_dataframe()
coord_names = ['lat', 'lon', 'section', 'lat_ship', 'lon_ship']
other_cols = [c for c in df.columns if c not in coord_names]
df = df[coord_names + other_cols]
df.to_csv("20241130_20250326_msfridtjofnansen_pamos_shipposition.csv", sep = ';', header = True)