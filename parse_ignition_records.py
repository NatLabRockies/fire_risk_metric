import pandas as pd
import glob
import numpy as np
import json
import matplotlib.pyplot as plt

# this script ingests California PUC ignition filings to approximate
# the liklihood of an ignition from different situations based on
# historical data
def read_ignition_reports(iginition_report_dir):
    ignition_reports = glob.glob(ignition_report_dir)
    columns=['Materials at Origin','Land Use at Origin','Fire Size',
            'Fire Suppressed by','Nominal Voltage','Equipment Type Associated to Ignition',
            'Type Of Construction','Outage','Suspected Initiating Event',
            'Equipment Facility Failure','Contact From Object',	'Contributing Factor']
    # categories are only used in some report sheets, if they are used, the column names are slightly different
    info_categories = ['Utility Name','Fire Start','Location', 'Fire', 'Utility Facility','Outage','Field Observations'] 
    cat_columns =['Materials at Origin','Land Use at Origin','Size',
            'Suppressed by','Nominal Voltage','Equipment Type Associated to Ignition',
            'Type','Was There an Outage','Suspected Ignition Cause',
            'Equipment/Facility Failure','Contact From Object',	'Contributing Factor'] 
    # some columns have an alternative name
    alt_columns = ['Material at Origin','Land Use at Origin','Size',
            'Suppressed by','Voltage\n(Volts)','Equipment Involved With Ignition',
            'Type','Was There an Outage','Suspected Initiating Event',
            'Equipment /Facility Failure','Contact From Object',	'Contributing Factor']
    alt2_columns = ['Material at Origin','Land Use at Origin','Size',
            'Suppressed \nby','Voltage','Equipment Involved With Ignition',
            'Type','Was There an Outage','Suspected Initiating Event',
            'Equipment /Facility \nFailure','Contact From \nObject',	'Contributing Factor']
    alt3_columns = ['Material at Origin','Land Use at Origin','Size',
            'Suppressed By','Voltage (KVolts)','Equipment Involved With Ignition',
            'Type','Was There an Outage','Suspected Initiating Event',
            'Equipment/Facility Failure','Contact From Object',	'Contributing Factor']
    alt4_columns = ['Material at Origin','Land Use at Origin','Size',
            'Suppressed by','Voltage\n(Volts)','Equipment Involved With Ignition',
            'Type','Was There an Outage','Suspected Ignition Cause',
            'Equipment /Facility Failure','Contact From Object',	'Contributing Factor']
    alt3_columns = []
    ignition_data = pd.DataFrame(columns)
    for report in ignition_reports:
        print(f'opening:{report}')
        if report.endswith('.csv'):
            df_i = pd.read_csv(report)
            df_i = df_i[columns]
            df_i = df_i.rename(columns={'Materials at Origin': 'Material at Origin',
                                   'Equipment Type Associated to Ignition': 'Equipment Involved With Ignition',
                                   'Type Of Construction': 'Type', 
                                   'Outage': 'Was There an Outage', 
                                   'Suspected Initiating Event': 'Suspected Ignition Cause',
                                   'Suppressed by': 'Suppressed'})
        elif report.endswith('.xlsx'):
            df_i = pd.read_excel(report, skiprows=1) # the first row will have categories,but we just need the column data
            if 'Nominal Voltage' in df_i.columns:
                df_i = df_i[columns]
                df_i = df_i.rename(columns = {'Equipment Type Associated to Ignition': 'Equipment Involved With Ignition',
                                        'Equipment/Facility Failure': 'Equipment Facility Failure'})
            elif 'Voltage\n(Volts)' in df_i.columns:
                if 'Suspected Ignition Cause' in df_i.columns:
                    df_i = df_i[alt4_columns]
                    df_i = df_i.rename(columns = {'Equipment /Facility Failure': 'Equipment Facility Failure'})
                else:
                    df_i = df_i[alt_columns]
                    df_i = df_i.rename(columns = {'Suspected Initiating Event': 'Suspected Ignition Cause',
                        'Equipment /Facility Failure': 'Equipment Facility Failure'})
            elif 'Voltage' in df_i.columns:
                df_i = df_i[alt2_columns]
                df_i = df_i.rename(columns = {'Suspected Initiating Event': 'Suspected Ignition Cause',
                                       'Equipment /Facility \nFailure': 'Equipment Facility Failure',
                                       'Contact From \nObject': 'Contact From Object',
                                       'Suppressed \nby': 'Suppressed by'
                                       })
            else: #'Voltage (KVolts)' in df_i.columns:
                df_i = df_i[alt3_columns]
                df_i = df_i.rename(columns = {'Suspected Initiating Event': 'Suspected Ignition Cause',
                                       'Equipment/Facility Failure': 'Equipment Facility Failure'})
        ignition_data = pd.concat([ignition_data, df_i], ignore_index=True)
    ignition_data.to_csv('all_iou_ignition_records.csv', index=False)

    return ignition_data

def plot_historical_histogram(ignition_counts):
    # for distribution factors, plot as if related only to bad configs,which are the first label in the list
    categories = ignition_counts['dist_factors'].keys()
    counts = [factor.values()[0] for factor in ignition_counts['dist_factors'].values()]
    plt.bar(categories, counts)
    plt.xlabel('Power System Characteristic')
    plt.ylabel('Count of Related Ignition Reports')
    plt.show()
    # for environmental factors, plot the ground vegetationin 3 plots(veg type, deciduous?, and management) 
    categories = ignition_counts['env_factors']['ground_veg']
    categories = ["Desert", "Savanna", "Grassland", "Forest", "Agriculture"]
    counts = []
    for category in categories:
        counts.append(ignition_counts['env_factors']['ground_veg'][category])
    plt.bar(categories, counts)
    plt.xlabel('Vegetation Type')
    plt.ylabel('Count of Related Ignition Reports')
    plt.show()

    categories = ["Deciduous", "Non-Deciduous"]
    counts = []
    for category in categories:
        counts.append(ignition_counts['env_factors']['ground_veg'][category])
    plt.bar(['Deciduous', 'Other'], counts)
    plt.xlabel('Deciduous Forest vs. Other Vegetation')
    plt.ylabel('Count of Related Ignition Reports')
    plt.show()

    categories = ["Managed", "Unmanaged", "Natural"]
    counts = []
    for category in categories:
        counts.append(ignition_counts['env_factors']['ground_veg'][category])
    plt.bar(['Managed', 'Disturbed', 'Natural'], counts)
    plt.xlabel('Type of Land Management')
    plt.ylabel('Count of Related Ignition Reports')
    plt.show()
    # for environmental factors, also plot lightning and wind speed on one

    categories = ["lightning", "wind_speed"]
    counts = []
    for category in categories:
        counts.append(ignition_counts["env_factors"][category].values()[0])
    plt.bar(categories, counts)
    plt.xlabel('Vegetation Type')
    plt.ylabel('Count of Related Ignition Reports')
    plt.show()


    return

def generate_liklihood_matrix(ignition_data, matrix_struct, export_name='ca_ious'):
    # the structure of the liklihood matrix follows the same structure as the matrix in quantify_fire_risk
    # in the liklihood_matrix each entry corresponds to the liklihood of that ignition type occuring based
    # on historical ignition records
    # The liklihood_matrix is used in quantify_fire_risk and element-wise multiplied by the fire risk matrix to get an overall score
    n_ign = len(ignition_data) # total number of reported ignitions
    ignition_probs = json.load('ignition_probs.json')
    ignition_counts = json.load('ignition_probs.json')
    # read in the ignition_report_to_metric_categories.json and query the ignition data
    # use those probabilities to fill in the ignition_probs.json
    report_labels_by_metric_name = json.load('ignition_report_to_metric_categories.json')
    factor_types = ['dist_factors', 'env_factors']
    for factor_type in factor_types:
        # EXAMPLE: dist_factor= "overhead", factor_labels= {"overhead":0, "padmount":0, "underground":0}
        for dist_factor, factor_labels in ignition_probs[factor_type].items():
            #EXAMPLE: factor_label= "padmount", factor_prob = 0
            for factor_label, factor_prob in factor_labels.items():
                report_categories = report_labels_by_metric_name[factor_type][dist_factor][factor_label]
                #EXAMPLE: report_column="Type", report_labels=["Padmounted","Padmount"]
                # some labels have more than one report category associated, so add those together
                for report_column, report_labels in report_categories.items():
                    #EXAMPLE: find all the entries where the type is Padmounted or Padmount and add that probability to the ignition_probs
                    factor_prob = min(1, factor_prob + len(ignition_data.loc[ignition_data[report_column].isin(report_labels)]) / n_ign)
                    ignition_count = min(n_ign, len(ignition_data.loc[ignition_data[report_column].isin(report_labels)]))
                    ignition_probs[factor_type][dist_factor][factor_label]=factor_prob
                    ignition_counts[factor_type][dist_factor][factor_label]=ignition_count
    # save a new ignition probability json
    with open(f"ignition_probs_{export_name}.json", "w") as file:
        json.dump(ignition_probs, file)
    with open(f"ignition_counts_{export_name}.json", "w") as file:
        json.dump(ignition_counts, file)
    return ignition_probs, ignition_counts

if __name__ == "__main__":
    ignition_report_dir = "ignition_reports/*"
    ignition_data = read_ignition_reports(ignition_report_dir)
    print(ignition_data)
    ignition_probs, ignition_counts = generate_liklihood_matrix(ignition_data)
    plot_historical_histogram(ignition_counts)


