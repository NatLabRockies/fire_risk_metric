from concurrent.futures import ProcessPoolExecutor, as_completed, wait
import multiprocessing
import os
import pandas as pd

# datasets can be downloaded with the below bash command from the below link
# aws s3 cp --no-sign-request s3://oedi-data-lake/SMART-DS/v1.0/ your_dir_here --recursive
# https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=SMART-DS%2F
# for example: aws s3 cp --no-sign-request s3://oedi-data-lake/SMART-DS/v1.0/2018/SFO/P28U/scenarios/solar_medium_batteries_low_timeseries/opendss_no_loadshapes/ examples\smart_ds_smbl_p28u\p28u\scenarios\solar_medium_batteries_low_timeseries\opendss\. --recursive

data_location = os.path.join('examples', 'smart_ds_smbl_p28u') #os.path.join('/datasets','SMART-DS','v1.0','2016','SFO')

def download_analysis_data():
    opendss_dir = os.path.join('examples', 'smart_ds_smbl_p28u','p28u','scenarios','solar_medium_batteries_low_timeseries','opendss')
    for subs in os.listdir(opendss_dir):
        if subs.startswith('p'):
            os.system(f'aws s3 cp --no-sign-request s3://oedi-data-lake/SMART-DS/v1.0/2018/SFO/P28U/scenarios/solar_medium_batteries_low_timeseries/opendss/{subs}/analysis/ examples/smart_ds_smbl_p28u/p28u/scenarios/solar_medium_batteries_low_timeseries/opendss//{subs}/analysis/. --recursive')
            print(f'uploading from {subs}/analysis')
            for feeder in os.listdir(os.path.join(opendss_dir, subs)):
                if feeder.startswith('p'):
                    print(f'uploading from {subs}/{feeder} to {subs}/{feeder}/analysis')
                    os.system(f'aws s3 cp --no-sign-request s3://oedi-data-lake/SMART-DS/v1.0/2018/SFO/P28U/scenarios/solar_medium_batteries_low_timeseries/opendss/{subs}/{feeder}/analysis/ examples/smart_ds_smbl_p28u/p28u/scenarios/solar_medium_batteries_low_timeseries/opendss//{subs}//{feeder}/analysis/. --recursive')


def run_analysis(region='p28u', scenario='solar_medium_batteries_low_timeseries'):
        metrics_location = os.path.join(data_location,region,'metrics.csv') #'Scenarios','solar_medium_batteries_low_timeseries','metrics.csv')
        metrics = pd.read_csv(metrics_location,header=0)

        overhead_map = {}
        line_overload_map = {}
        transformer_overload_map = {}

        for idx,row in metrics.iterrows():
            feeder = row['Feeder Name']
            substation = row['Substation Name']
            if feeder == 'subtransmission':
                continue
            underground_percent = row['Overhead Percentage of Medium Voltage Line Miles']
            number_transformers = row['Number of Transformers']
            total_line_length = row['Medium Voltage Length (miles)']
            transformer_overload_data = pd.read_csv(os.path.join(data_location,region,'scenarios',scenario,'opendss',substation,feeder,'analysis','peak_transformer_overloads.csv'),header=0)
            if number_transformers == 0:
                transformer_overload_ratio = 0
            else:
                transformer_overload_ratio = len(transformer_overload_data)/number_transformers
            line_overload_data = pd.read_csv(os.path.join(data_location,region,'scenarios',scenario,'opendss',substation,feeder,'analysis','peak_line_overloads.csv'),header=0)
            all_lines = set()
            for idx,row in line_overload_data.iterrows():
                all_lines.add(row['Name'])
           
            total_overload_miles = 0
            with open(os.path.join(data_location,region,'scenarios',scenario,'opendss',substation,feeder,'Lines.dss'),'r') as lines_file:
                for row in lines_file.readlines():
                    sp = row.split()
                    overloaded = False
                    for token in sp:
                        if token.startswith('Line.'):
                            if token in all_lines:
                                overloaded = True
                        if token.startswith('Length='):
                            length = token.split('=')[1]
                            length = float(length)*0.621371
                            total_overload_miles+=length
            line_overload_ratio = total_overload_miles/total_line_length
            overhead_map[feeder] = 100-underground_percent
            line_overload_map[feeder] = line_overload_ratio
            transformer_overload_map[feeder] = transformer_overload_ratio
        return (overhead_map,transformer_overload_map,line_overload_map)

def collect_region_stats():
    all_regions = []
    results = []
    for region in  os.listdir(data_location):
        if region.startswith('p'):
            all_regions.append(region)
            result = run_analysis(region)
            results.append(result)

    # comment out the two lines above and uncomment the below for multi-processing
    #nprocs = multiprocessing.cpu_count()
    #pool = multiprocessing.Pool(processes=nprocs)
    #results = pool.map(run_analysis, all_regions) #Format is (overhead_map, transformer_overload_map, line_overload_map)
    #pool.close()
    #pool.join()

    all_overhead_map = {}
    all_transformer_overload_map = {}
    all_line_overload_map = {}

    for overhead_map, transformer_overload_map,line_overload_map in results:
        all_overhead_map.update(overhead_map)
        all_transformer_overload_map.update(transformer_overload_map)
        all_line_overload_map.update(line_overload_map)


    result = pd.DataFrame(columns=['feeder','percentage overhead','percentage transformers overloaded','percentage line length overloaded','risk factor'])
    cnt = 0
    for feeder in all_overhead_map:
        risk_factor = all_overhead_map[feeder]+all_transformer_overload_map[feeder]+all_line_overload_map[feeder]
        result.loc[cnt] = (feeder,all_overhead_map[feeder],all_transformer_overload_map[feeder],all_line_overload_map[feeder],risk_factor)
        cnt+=1
    #result = result.sort_values(by=['risk factor','feeder'],ascending=False)
    result.to_csv('smbl_summary.csv',header=True,index=False)

if __name__ =='__main__':
    #download_analysis_data()
    collect_region_stats()