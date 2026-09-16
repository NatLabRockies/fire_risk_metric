import opendssdirect as odd
import sys
import pathlib
import pyproj
import json
import pandas as pd
# this script runs through the opendss files of a power system model
# and applies the fire risk metric which quantifies the risk of the
# power system igniting a fire
dist_trait_names = ['line_to_veg_dist', 'line_to_line_dist', 'line_to_gnd_dist', 'line_age',
                    'transformer_age', 'oil_type_transformer', 'overhead', 'uninsulated',
                    'line_peak_load', 'transformer_peak_load', 'hif_detection', 'powersafety_shutoff',
                    'fuse_type', 'response_team_coordination', 'high_fidelity_tracking', 'pole_type']
# hif_detection reduces risk if there is monitoring to prevent arcing particularly with vegetation contact
# fuse type reduces risk if they are non-expulsionary fuses, if they are reclosers that can adjust settings in that order
# pole type reduces risk if it is a higher pole class, a wrapped pole, an aluminum, steel, or iron pole in that order

terrain_trait_names = ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed', 'ambient_temp']

def get_dist_fire_traits(power_model, dist_fire_components):
    # check the risks we know just by looking at the distribution model 
    # default to 0
    n_traits = len(dist_trait_names)
    #dist_fire_components = []
    #dist_risk_scores = {}
    ##### TODO: run model at peak load and export line currents and transformer currents
    # go through all components and check risk factors
    for dfc in dist_fire_components.keys():
        dist_risk_scores[dfc.name] = {}
        risk_score = [0]*n_traits
        overhead = False
        # check line features
        if dfc.name.startswith('Line'):
            # check age
            if dfc:
                risk_score[3] = 0
            #check if overhead, denoted in line code. OH for high voltage or non-inner city lines
            if 'OH' in dfc.LineCode: # need to double check ODSS line code call
                risk_score[6] = 10
                overhead = True
            # check if insulated. True for low voltage in city or UG lines
            if overhead and dfc.Voltage>120:
                risk_score[7] = 10
            # check line peak current
            ######
            # TODO: use run of peak load and check current vs. rating
            ######
        # check transformer features
        if dfc.name.startswith('Transformer'):
            # check if oil
            if dfc:
                risk_score[5] = 10
            # check transformer peak current
            #######
            # TODO: use run of peak load and check current vs. rating
            #######
        # check resilience features
        # high impedance fault detection is still an area of research, power
        # safety shutoffs are only used in some areas of California
        # misting fire hose nozzles near high voltage lines were only applied in China
        # response team coordination is difficult to quantify
        # most fire response teams have 1km resolution sattelite tracking
        risk_score[10] = 10 # high impedance fault detection
        risk_score[11] = 5 # power safety shutoffs
        risk_score[12] = 10 # fuse_type
        risk_score[13] = 5 # response team coordination
        risk_score[14] = 1 # high fidelity tracking
        # add risk score to json
        dist_fire_components[dfc.name]['score'] = risk_score
    # export distribution risk score to json format
    with open('dist_risk_scores.json', 'w') as dist_score_file:
        json.dump(dist_fire_components, dist_score_file)
    return dist_fire_components

def get_dist_fire_locations(power_model_dir):
    dist_coord_frame = pyproj.Proj(init='epsg:32610')
    lon_lat_coord_frame = pyproj.Proj(init='epsg:5070')
    dist_fire_components = {} # add something to read all from model
    region_name = str(power_model_dir).split('/')[-1]
    sub_regions = []
    potential_sub_regions = power_model_dir.glob('*')
    for folder in potential_sub_regions:
        sub_region_name = str(folder).split('/')[-1]
        if sub_region_name.startswith(region_name) and (folder / "DSSfiles/Buscoords.dss").exists() and (folder / "DSSfiles/Transformers.dss").exists():
            sub_regions.append(folder)
            trans_file = (sub_region / "DSSfiles/Transformers.dss")
            line_file = (sub_region / "DSSfiles/Lines.dss")
            bus_file = (sub_region / "DSSfiles/Buscoords.dss")
            linecode_file = (sub_region / "DSSfiles/LineCodes.dss")
            # read in bus coordinates
            bus_coords = {}
            with open(bus_file, 'r') as bf:
                bus_coord_lines = bf.readlines()
                for line in bus_coord_lines:
                    if len(line)>4:
                        bus_entry = line.split(' ')
                        bus_name = bus_entry[0]
                        bus_x = bus_entry[1]
                        bus_y = bus_entry[2]
                        bus_coord = pyproj.transform(dist_coord_frame, lon_lat_coord_frame, bus_x, bus_y) 
                        bus_coords[bus_name] = bus_coord
            # read in line codes
            line_codes = {}
            with open(linecode_file, 'r') as lcf:
                lcf_lines = lcf.readlines()
                for line in lcf_lines:
                    if len(line)>4:
                        code_entry = line.split(' ')
                        code_name = code_entry[1].replace('Linecode.', '')
                        normamps = code_entry[-1].replace('normamps=', '')
                        line_codes[code_name] = normamps
            # read in lines
            with open(line_file, 'r') as lf:
                lf_lines = lf.readlines()
                for line in lf_lines:
                    if len(line)>4:
                        line_entry = line.split(' ')
                        name = line_entry[1]
                        bus1 = line_entry[3].replace('bus1=', '').split('.')[0]
                        bus2 = line_entry[4].replace('bus2=', '').split('.')[0]
                        linecode = line_entry[-1].replace('Linecode=', '')
                        # add info to dictionary
                        dist_fire_components[name] = {}
                        dist_fire_components[name]['coords'] = [bus_coords[bus1]]
                        dist_fire_components[name]['coords'].append(bus_coords[bus2])
                        dist_fire_components[name]['normamps'] = line_codes[linecode]
            # read in transformers
            with open(trans_file, 'r') as tf:
                tf_lines = tf.readlines()
                for line in tf_lines:
                    if len(line)>4:
                        line_entry = line.split(' ')
                        name = line_entry[1]
                        bus = line_entry[8].replace('bus=', '')
                        # add info to dictionary
                        dist_fire_components[name] = {}
                        dist_fire_components[name]['coords'] = [bus_coords[bus]]
                        dist_fire_components[name]['normamps'] = 1000000000 # need to find a way to add rating
    return dist_fire_components

def get_terrain_coords(soil_file, soil_moisture_file, veg_file, lightning_file, burnprob_file):
    # parse the files and select only the bay area: as defined as
    # north to Sacremento: 38.5816N 121.4944W, 
    # south and east to Fresno: 36.7378N 119.7871W, 
    # and west to longitude 120W (west is negative?)
    terrain_component_coords = {}
    terrain_component_coords["type"] = "FeatureCollection"
    terrain_component_coords["features"] = []

    # get table for soil saturation
    soil_table = pd.read_csv(soil_file)
    soil_table = soil_table[['Region', 'Latitude', 'Longitude', 'Species', 'Soil_type', 'Soil_drainage',
                            'Ecosystem_type', 'Ecosystem_state', 'Leaf_habit']]
    soil_table = soil_table[soil_table['Region']=='California']
    moisture_table = pd.read_csv(soil_moisture_file)
    moisture_table = moisture_table[['date', 'time', 'latitude', 'longitude', 'soil_moisture']]
    #for sd, lat, long in zip(soil_table['Soil_drainage'], soil_table['Latitude'], soil_table['Longitude']):#soil_table['Soil_type']):
    #    # not sure we need anything for soil type
    #    if sd=='Dry':
    #        risk = 10
    #    elif sd=='Wet':
    #        risk = 0
    #    else:
    #        risk=0
    moisture_risk_list=[]
    soil_risk_list = []
    for sm, lat, long, date, time in zip(moisture_table['soil_moisture'], moisture_table['latitude'], moisture_table['longitude'], moisture_table['date'], moisture_table['time']):
        risk = (1-float(sm))*10
        if risk == 'nan' or np.isnan(risk):
            print('nan risk for soil moisture')
            pass
        # add rainfall data interrelated with soil drainage to get overall saturation
        #rain_table = pd.read_csv(precip_file)
        
        # add soil risk to geojson
        if risk<=11 and risk>=0:
            soil_entry = {}
            soil_entry["type"]="Feature"
            soil_entry["geometry"] = {}
            soil_entry["geometry"]["type"] = "Point"
            soil_entry["geometry"]["coordinates"] = (lat, long)
            soil_entry["properties"]={}
            soil_entry["properties"]["soil_sat"]=risk
            soil_entry["properties"]["date"] = date
            soil_entry["properties"]["time"] = time
            moisture_risk_list.append(soil_entry)
            terrain_component_coords["features"].append(soil_entry)
    print('soil saturation risk added to json')
    # get table for lightning
    lf = netCDF4.Dataset(lightning_file)
    flashes = lf.variables['VHRMC_LIS_FRD'] # mean flashes for each month at long and lat in flashes/km2/day
    months, latitude, longitude = flashes.get_dims()
    months = lf.variables[months.name]
    latitude = lf.variables['Latitude']
    longitude = lf.variables['Longitude']
    print(f"months: {months[0]} to {months[-1]}, \
        lat: {latitude[0]} to {latitude[-1]}, \
        long: {longitude[0]} to {longitude[-1]} \
        resolution of {latitude[1]-latitude[0]} degrees,") #\
    #    flash range: {min(flashes)} to {max(flashes)}")
    # pull out for SFO bay area and convert to geojson
    flash_risk_list = []
    for month in months:
        month = float(month)
        lat_i = 0
        for lat in latitude:
            lat = float(lat)
            if lat>36.7378 and lat<38.5816:
                long_i = 0
                for long in longitude:
                    long = float(long)
                    if long>-120 and long<-119.7871:#119.7871 and long<120:
                        flash = flashes[int(month-1), lat_i, long_i] #[month][lat][long]
                        if flash == 'nan' or np.isnan(flash) :
                            print('nan risk for flashes')
                            pass
                        elif risk<=100 and risk>=0 and month<=12:
                            risk = flash/0.05 * 10 # normalize with 0.05 and then scale to 10 point scale
                            # add risk to geojson
                            lightning_entry = {}
                            lightning_entry["type"]="Feature"
                            lightning_entry["geometry"] = {}
                            lightning_entry["geometry"]["type"] = "Point"
                            lightning_entry["geometry"]["coordinates"] = (lat, long)
                            lightning_entry["properties"]={}
                            lightning_entry["properties"]["flash"]=risk
                            lightning_entry["properties"]["month"]=month
                            flash_risk_list.append(lightning_entry)
                            terrain_component_coords["features"].append(lightning_entry)
                    long_i = long_i+1
            lat_i = lat_i+1
    print('lightning risk added to json')
    # convert ecosystem type and state into fire risk value
    vegetation_risk = 0
    veg_risk_list = []
    for ess, est, lh, lat, long in zip(soil_table['Ecosystem_state'], soil_table['Ecosystem_type'], soil_table['Leaf_habit'], soil_table['Latitude'], soil_table['Longitude']):
        lat = float(lat)
        long = float(long)
        if ess == 'Managed':
            risk = 0
        elif ess == 'Unmanaged': #unmanaged means it was managed or disturbed by people in the past
            risk = 10
        else: # if it's natural
            risk = 5
        vegetation_risk=risk
            
        if est == 'Desert':
            risk = 10
        elif est == 'Savanna':
            risk = 9
        elif est == 'Grassland':
            risk = 8
        elif est == 'Shrubland':
            risk = 7
        elif est == 'Forest':
            risk = 6
        elif est == 'Agriculture':
            risk = 5
        else: # nan's 0s
            risk = 0
        vegetation_risk = (vegetation_risk + risk)/2
        for month in range(1,12):
            if lh =='Deciduous':
                if month>=9 and month<=11:
                    risk = 5
                else:
                    risk = 3
            else: # if evergreen
                risk = 5
            vegetation_risk = (vegetation_risk*2 + risk)/3
            if risk == 'nan' or np.isnan(risk):
                print('nan risk in vegetation')
            elif risk <=11 and risk>=0 and lat<39.0 and lat>36.0 and long>-122.0 and long<-118.0:
                # add risk to geojson
                veg_entry = {}
                veg_entry["type"]="Feature"
                veg_entry["geometry"] = {}
                veg_entry["geometry"]["type"] = "Point"
                veg_entry["geometry"]["coordinates"] = (lat, long)
                veg_entry["properties"]={}
                veg_entry["properties"]["veg_type"]=vegetation_risk
                veg_entry["properties"]["month"]=month
                veg_risk_list.append(veg_entry)
                terrain_component_coords["features"].append(veg_entry)
    print('vegetation type risk added to json')
    terrain_risk_no_nan = {}
    terrain_risk_no_nan["type"] = "Feature Collection"
    terrain_risk_no_nan["features"] = {}
    terrain_risk_no_nan["features"]["veg_type"] = []
    terrain_risk_no_nan["features"]["lightning"] = []
    terrain_risk_no_nan["features"]["soil_type"] = []
    terrain_risk_no_nan["features"]["soil_moisture"] = []
    terrain_risk_no_nan["features"]["extra"] = []
    for feature in terrain_component_coords["features"]:
        if np.isnan(feature["geometry"]["coordinates"][0]) or np.isnan(feature["geometry"]["coordinates"][1]):
            pass
        elif "date" in feature["properties"].keys() and not isinstance(feature["properties"]["date"], str): #np.isnan(feature["properties"]["date"]):
            pass
        elif "time" in feature["properties"].keys() and not isinstance(feature["properties"]["time"], str):
            pass
        elif "month" in feature["properties"].keys() and np.isnan(feature["properties"]["month"]):
                pass
        elif "veg_type" in feature["properties"].keys():
            if np.isnan(feature["properties"]["veg_type"]):
                pass
            else:
                terrain_risk_no_nan["features"]["veg_type"].append(feature)
        elif "flash" in feature["properties"].keys():
            if np.isnan(feature["properties"]["flash"]):
                pass
            else:
                terrain_risk_no_nan["features"]["lightning"].append(feature)
        elif "soil_sat" in feature["properties"].keys():
            if np.isnan(feature["properties"]["soil_sat"]):
                pass
            else:
                terrain_risk_no_nan["features"]["soil_moisture"].append(feature)
        else:
            terrain_risk_no_nan["features"]["extra"].append(feature)
    
    with open('terrain_risk_scores.json', 'w') as terr_score_file:
        json.dump(terrain_risk_no_nan, terr_score_file)
    print('terrain risk factors recorded in terrain_risk_scores.json')
    return terrain_component_coords, moisture_risk_list, flash_risk_list, veg_risk_list


def distribution_terrain_risk_matrix():
    dist_terr_cross_list = [['ground_veg', 'veg_moisture', 'wind_speed', 'ambient_temp'],                                   #line to veg
                            ['ground_veg', 'wind_speed', 'ambient_temp'],                                                   #line to line
                            ['ground_veg', 'soil_saturation', 'wind_speed', 'ambient_temp'],                                #line to ground
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed', 'ambient_temp'],   #line age
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'ambient_temp'],                 #xfmr age
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'ambient_temp'],                 #oil xfmr
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed'],                   #OH
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'wind_speed', 'ambient_temp'],                #uninsulated
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'wind_speed', 'ambient_temp'],                #line peak
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'wind_speed'],                                #xfmr peak
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed', 'ambient_temp'],   #hif
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed'],                   #PSPS
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed', 'ambient_temp'],   #fuse type
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed', 'ambient_temp'],   #response
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed', 'ambient_temp'],   #tracking
                            ['ground_veg', 'soil_saturation', 'veg_moisture', 'lightning', 'wind_speed']]                   #pole type
    return dist_terr_cross_list

def quantify_fire_risk(power_model_dir, fire_gis_dir):
    # start with a fire risk of zero and slowly add to that
    total_fire_risk = 0
    # initialize list of terrain traits
    # establish fire risk correlations
    dist_terr_cross_list = distribution_terrain_risk_matrix()
    # load the power model
    power_model = odd.run_command(str(power_model_dir / 'DSSfiles/Master.dss'))
    # get locations for power system components and assign locations to fire risk traits
    dist_fire_components = get_dist_fire_locations(power_model_dir)
    # get power model traits according to metric
    dist_fire_components = get_dist_fire_traits(power_model, dist_fire_components)
    # get locations for fire susceptible attributes
    terrain_component_coords = get_terrain_coords(fire_gis_dir)
    # if grid fire risk traits and landscape/climate fire risk traits are within
    # __ meters of each other, consider them co-located and multiply
    dist_index = 0
    for ps_comp in dist_fire_components.keys():
        ps_coord_list = dist_fire_components[ps_comp]['coords']
        terrain_index = 0
        # check distances between distribution system risks and environmental risks
        ##### TODO: alter the below to create loop where distance from transformers (points) and lines (line) to 
        ##### environmental risk areas (polygons) are captured
        for tc_coord in terrain_component_coords:
            if (terrain_trait_names[terrain_index] in dist_terr_cross_list[dist_index]) and abs(ps_coord-tc_coord) <= 0.001:
                total_fire_risk += dist_trait_score[dist_index] * terrain_trait_score[terrain_index]
            terrain_index += 1
        dist_index += 1
        #####
    return total_fire_risk

def historical_probability_matrix(historical_ignition_csv):
    # historical ignition data is used to determine the liklihood of an ignition being
    # caused by a certain combination of characteristics
    # the alignment is described with the 'risk_descriptor':{historical_data_heading:[relevant,ignitionevent,tags]}
    # a zero is a placeholder after characteristics that aren't described in historical data
    hist_df = pd.read_csv(historical_ignition_csv)
    n_ignitions = len(hist_df)
    # first set up mapping from distribution traits to labels in the historical ignitions
    dist_trait_to_label = {'line_to_veg_dist':{'Suspected Ignition Cause':['Contact - Customer(Equip/Structure/Veg)', 'Contact from Object', 'Vegetation']},
                    'line_to_line_dist':{'Suspected Ignition Cause': ['Wire-Wire Contact', 'Wire-to-wire contact']}, 
                    'line_to_gnd_dist':0,
                    'line_age':{'Equipment Facility Failure': ['Conductor', 'Conductor*', 'SECONDARY CONDUCTOR OH', 'Service Drop']},
                    'transformer_age':{'Equipment Facility Failure':['Transformer', 'Transformer failure']},
                    'oil_type_transformer':0, 
                    'overhead':{'Type': ['Overhead', 'DISTRIBUTION']},
                    'uninsulated': {'Equipment Involved With Ignition': ['Conductor', 'Conductor*', 'Secondary Conductor', 'Service Drop']},
                    'line_peak_load': {'Equipment Facility Failure': ['Conductor', 'Conductor*', 'SECONDARY CONDUCTOR OH', 'Service Drop', 'Tie Wire', 'Tie wire failure', 'WIRE-TO-WIRE CONTACT']},
                    'transformer_peak_load':{'Equipment Involved With Ignition':['Transformer', 'Transformer Bushing']}, 
                    'hif_detection':0, 
                    'powersafety_shutoff':0,
                    'fuse_type':{'Equipment Involved With Ignition':['Recloser', 'Switch', 'Circuit Breaker', 'Open Link Fuse', 'Fuse', 'E Fuse']}, 
                    'response_team_coordination':{'Suppressed':['Patrol', 'CalFire', 'Fire Agency']}, 
                    'high_fidelity_tracking':0, 
                    'pole_type':{'Equipment Involved With Ignition':['Pole', 'Cross Arm', 'Crossarm'], 'Equipment Facility Failure':['Pole', 'Pole Failure', 'CROSS ARM', 'crossarm', 'crossarm failure']}
    }
    # then set up mappings from terrain descriptions to labels in the historical ignitions
    terrain_to_label = {'ground_veg':{'Material at Origin', 'Land Use at Origin'},
                         'soil_saturation':0, 
                         'veg_moisture':0, 
                         'lightning':{'Suspected Ignition Cause': ['Weather - Lightning']},
                         'wind_speed':{'Suspected Ignition Cause':['Weather - High Wind', 'Wire-Wire Contact', 'Wire-to-wire Contact']},
                         'ambient_temp':0 }

    return historical_probability_matrix

if __name__=="__main__":
    power_model_dir = sys.argv[1]
    if isinstance(power_model_dir, str):
        power_model_dir = pathlib.Path(power_model_dir)
    fire_gis_dir = sys.argv[2]
    if isinstance(fire_gis_dir, str):
        fire_gis_dir = pathlib.Path(fire_gis_dir)
    total_fire_risk = quantify_fire_risk(power_model_dir, fire_gis_dir)
    print(total_fire_risk)
