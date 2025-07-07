# -*- coding: utf-8 -*-

#Requirements
#------------
# - Python 3.7+
# - numpy
# - pandas
# - matplotlib
# - tqdm
#
# Install dependencies with:
# pip install numpy pandas matplotlib tqdm

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

base_dir = "/your/data/path"

def make_msd_csv(file_name, time_interval, output_folder):
    def _calc_msd(df, interval):
        msds = np.zeros(1)
        for i in range(1, len(df)):
            sd = 0
            for col in ["POSITION_X", "POSITION_Y"]:
                x = df[col].values
                sd += np.power((x[i:] - x[:-i]), 2)
            msds = np.append(msds, np.average(sd))
        intervals = np.append(np.zeros(1), range(1, len(df))) * interval
        df = pd.DataFrame({"interval": intervals, "msd": msds})
        return df.reset_index(drop=True)

    df_tracks = pd.read_csv(file_name, header=0, skiprows=[1, 2, 3, 4])

    df_tracks = df_tracks[["TRACK_ID", "POSITION_T", "POSITION_X", "POSITION_Y"]]
    df_tracks = df_tracks.sort_values(by=["TRACK_ID", "POSITION_T"])
    df_tracks = df_tracks.reset_index(drop=True)

    grouped = df_tracks.groupby(["TRACK_ID"], as_index=False, group_keys=False)
    df_new = grouped.apply(lambda x: _calc_msd(x, time_interval)).reset_index(drop=True)

    df = pd.concat([df_tracks, df_new], axis=1)

    # Ensure the output folder exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    output_file = os.path.join(output_folder, os.path.basename(file_name).replace(".csv", "_msd.csv"))
    df.to_csv(output_file, index=False)
    return output_file

def plot_msd(file_name, output_folder):
    # Read the MSD data from the CSV file
    df = pd.read_csv(file_name)

    # Get unique track IDs
    unique_track_ids = df["TRACK_ID"].unique()

    # Create an output folder within the specified working directory if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Initialize tqdm progress bar
    progress_bar = tqdm(total=len(unique_track_ids), desc="Plotting")

    # Plot MSD for each track ID and save the plot in the output folder
    for track_id in unique_track_ids:
        track_data = df[df["TRACK_ID"] == track_id]
        plt.plot(track_data["interval"], track_data["msd"], label=f"Track {track_id}")

        # Save the plot in the output folder
        plt.xlabel("Time Interval")
        plt.ylabel("MSD")
        plt.title(f"Mean Squared Displacement (MSD) for Track {track_id}")
        plt.savefig(os.path.join(output_folder, f"track_{track_id}_msd.png"))
        plt.close()

        # Update progress bar
        progress_bar.update(1)

    # Close the progress bar
    progress_bar.close()

# Set the working directory (replace with your specific working directory)
working_dir = "/Users/yourname/data"      # Rename this path as needed
time_interval = 0.2  # seconds

# Traverse through the working directory and its subfolders
for root, dirs, files in os.walk(working_dir):
    # Search for all CSV files in the current directory
    csv_files = [os.path.join(root, x) for x in files if x.endswith(".csv")]

    # Check if there are any CSV files
    if len(csv_files) == 0:
        print(f"ERROR: There are no CSV files in {root}")
    else:
        # Process each CSV file
        for csv_file in csv_files:
            print(f"Processing file: {csv_file}")

            # Create an output folder for MSD CSVs within the current subfolder
            msd_csv_output_folder = os.path.join(root, "msd_csv")
            msd_csv_file = make_msd_csv(csv_file, time_interval, msd_csv_output_folder)

            # Create an output folder for MSD plots within the current subfolder
            plot_output_folder = os.path.join(root, "msd_plots")
            plot_msd(msd_csv_file, plot_output_folder)

print("Processing completed.")

def find_all_msd_csv(subfolder):
    # Initialize a list to store paths of CSV files
    msd_files = []

    # Walk through the subfolder
    for root, dirs, files in os.walk(subfolder):
        for file in files:
            if 'msd' in file and file.endswith('.csv'):
                msd_files.append(os.path.join(root, file))

    return msd_files

def merge_msd_csvs(subfolder, output_csv):
    # Find all MSD CSV files in the specified subfolder
    msd_files = find_all_msd_csv(subfolder)

    # If no MSD CSV files are found, print an error message and return
    if not msd_files:
        print(f"Error: No MSD CSV files found in the subfolder {subfolder}.")
        return

    # Initialize an empty DataFrame to hold all MSD data
    merged_df = pd.DataFrame()

    # Iterate over each MSD file with progress bar
    for file_path in tqdm(msd_files, desc=f"Merging MSD files in {subfolder}"):
        # Read the MSD data from the CSV file
        df = pd.read_csv(file_path)
        # Add a column to identify the source file
        df['source_file'] = os.path.basename(file_path)
        # Append the data to the merged DataFrame
        merged_df = pd.concat([merged_df, df], ignore_index=True)

    # Save the merged DataFrame to a CSV file
    merged_df.to_csv(output_csv, index=False)
    print(f"Merged CSV saved as {output_csv}")

def plot_merged_msd(output_csv, output_file, x_limit=None, y_limit=None):
    # Read the merged MSD data from the CSV file
    merged_df = pd.read_csv(output_csv)

    # Initialize the figure
    plt.figure(figsize=(12, 8))

    # Define colors for different source files
    unique_files = merged_df['source_file'].unique()
    colors = plt.cm.get_cmap('tab20', len(unique_files))

    # Initialize a counter for the number of curves plotted
    curve_count = 0

    # List to store legend entries
    legend_labels = []

    # Iterate over each source file
    for i, file_name in enumerate(tqdm(unique_files, desc="Plotting MSD data")):
        # Filter data for the current file
        file_data = merged_df[merged_df['source_file'] == file_name]

        # Get all unique track IDs
        unique_track_ids = file_data["TRACK_ID"].unique()

        # Plot MSD for each track ID
        for track_id in unique_track_ids:
            track_data = file_data[file_data["TRACK_ID"] == track_id].head(31)  # Select first 30 intervals
            plt.plot(track_data["interval"], track_data["msd"], color=colors(i), alpha=0.7)

            # Increment the curve count for each track
            curve_count += 1

        # Append an entry to the legend with the count of curves for this source file
        legend_labels.append(f"{file_name} (Curves: {len(unique_track_ids)})")

    # Add labels, title, and legend to the plot
    plt.xlabel("Time Interval (s)")
    plt.ylabel("MSD")
    plt.title("Mean Squared Displacement (MSD) for All Tracks (First 30 Intervals)")

    # Set x and y limits if provided
    if x_limit is not None:
        plt.xlim(x_limit)
        print(f"X-axis limits set to: {x_limit}")
    if y_limit is not None:
        plt.ylim(y_limit)
        print(f"Y-axis limits set to: {y_limit}")

    # Display the legend with the curve counts included
    plt.legend(legend_labels, loc="upper right", bbox_to_anchor=(1.05, 1), title="Source Files", fontsize=10)

    # Save the combined plot to the specified output file
    plt.savefig(output_file, dpi=300, bbox_inches="tight")  # Save with higher resolution and tight layout
    plt.close()

    # Print the total number of curves in the console
    print(f"Total number of curves plotted: {curve_count}")



def process_subfolders(base_dir, x_limit=None, y_limit=None):
    # Iterate through each subfolder in the base directory
    for subfolder in os.listdir(base_dir):
        subfolder_path = os.path.join(base_dir, subfolder)
        msd_csv_path = os.path.join(subfolder_path, "msd_csv")
        msd_merge_path = os.path.join(subfolder_path, "msd_merge")

        if os.path.isdir(subfolder_path) and os.path.isdir(msd_csv_path):
            print(f"Processing subfolder: {subfolder_path}")

            # Create the msd_merge subfolder if it doesn't exist
            os.makedirs(msd_merge_path, exist_ok=True)

            # Define paths for the merged CSV and output plot
            merged_csv = os.path.join(msd_merge_path, "merged_msd_data.csv")
            output_file = os.path.join(msd_merge_path, "all_tracks_msd_first_30_intervals.png")

            # Merge MSD CSV files in the msd_csv subfolder
            merge_msd_csvs(msd_csv_path, merged_csv)

            # Plot the merged MSD data
            plot_merged_msd(merged_csv, output_file, x_limit, y_limit)

# Example usage:
base_dir = "/your/data/"  # Update this path as needed
x_limit = (0,6)  # Example x-axis limit
y_limit = (0,0.5)# Example y-axis limit

# Process each subfolder in the base directory with specified limits
process_subfolders(base_dir, x_limit, y_limit)

#print(merged_df.head())

"""### plotting"""

def find_all_msd_csv(subfolder):
    # Initialize a list to store paths of CSV files
    msd_files = []

    # Walk through the subfolder
    for root, dirs, files in os.walk(subfolder):
        for file in files:
            if 'msd' in file and file.endswith('.csv'):
                msd_files.append(os.path.join(root, file))

    return msd_files

def merge_msd_csvs(subfolder, output_csv):
    # Find all MSD CSV files in the specified subfolder
    msd_files = find_all_msd_csv(subfolder)

    # If no MSD CSV files are found, print an error message and return
    if not msd_files:
        print(f"Error: No MSD CSV files found in the subfolder {subfolder}.")
        return

    # Initialize an empty DataFrame to hold all MSD data
    merged_df = pd.DataFrame()

    # Iterate over each MSD file with progress bar
    for file_path in tqdm(msd_files, desc=f"Merging MSD files in {subfolder}"):
        # Read the MSD data from the CSV file
        df = pd.read_csv(file_path)
        # Add a column to identify the source file
        df['source_file'] = os.path.basename(file_path)
        # Append the data to the merged DataFrame
        merged_df = pd.concat([merged_df, df], ignore_index=True)

    # Save the merged DataFrame to a CSV file
    merged_df.to_csv(output_csv, index=False)
    print(f"Merged CSV saved as {output_csv}")

def plot_merged_msd(output_csv, output_file, x_limit=None, y_limit=None):
    # Read the merged MSD data from the CSV file
    merged_df = pd.read_csv(output_csv)

    # Initialize the figure
    plt.figure(figsize=(12, 8))

    # Define colors for different source files
    unique_files = merged_df['source_file'].unique()
    colors = plt.cm.get_cmap('tab20', len(unique_files))

    # Initialize a counter for the number of curves plotted
    curve_count = 0

    # List to store legend entries
    legend_labels = []

    # Iterate over each source file
    for i, file_name in enumerate(tqdm(unique_files, desc="Plotting MSD data")):
        # Filter data for the current file
        file_data = merged_df[merged_df['source_file'] == file_name]

        # Get all unique track IDs
        unique_track_ids = file_data["TRACK_ID"].unique()

        # Plot MSD for each track ID
        for track_id in unique_track_ids:
            track_data = file_data[file_data["TRACK_ID"] == track_id].head(31)  # Select first 30 intervals
            plt.plot(track_data["interval"], track_data["msd"], color=colors(i), alpha=0.7)

            # Increment the curve count for each track
            curve_count += 1

        # Append an entry to the legend with the count of curves for this source file
        legend_labels.append(f"{file_name} (Curves: {len(unique_track_ids)})")

    # Add labels, title, and legend to the plot
    plt.xlabel("Time Interval (s)")
    plt.ylabel("MSD")
    plt.title("Mean Squared Displacement (MSD) for All Tracks (First 30 Intervals)")

    # Set x and y limits if provided
    if x_limit is not None:
        plt.xlim(x_limit)
        print(f"X-axis limits set to: {x_limit}")
    if y_limit is not None:
        plt.ylim(y_limit)
        print(f"Y-axis limits set to: {y_limit}")

    # Display the legend with the curve counts included
    plt.legend(legend_labels, loc="upper right", bbox_to_anchor=(1.05, 1), title="Source Files", fontsize=10)

    # Save the combined plot to the specified output file
    plt.savefig(output_file, dpi=300, bbox_inches="tight")  # Save with higher resolution and tight layout
    plt.close()

    # Print the total number of curves in the console
    print(f"Total number of curves plotted: {curve_count}")



def process_subfolders(base_dir, x_limit=None, y_limit=None):
    # Iterate through each subfolder in the base directory
    for subfolder in os.listdir(base_dir):
        subfolder_path = os.path.join(base_dir, subfolder)
        msd_csv_path = os.path.join(subfolder_path, "msd_csv")
        msd_merge_path = os.path.join(subfolder_path, "msd_merge")

        if os.path.isdir(subfolder_path) and os.path.isdir(msd_csv_path):
            print(f"Processing subfolder: {subfolder_path}")

            # Create the msd_merge subfolder if it doesn't exist
            os.makedirs(msd_merge_path, exist_ok=True)

            # Define paths for the merged CSV and output plot
            merged_csv = os.path.join(msd_merge_path, "merged_msd_data.csv")
            output_file = os.path.join(msd_merge_path, "all_tracks_msd_first_30_intervals.png")

            # Merge MSD CSV files in the msd_csv subfolder
            merge_msd_csvs(msd_csv_path, merged_csv)

            # Plot the merged MSD data
            plot_merged_msd(merged_csv, output_file, x_limit, y_limit)

# Example usage:
base_dir = "/Users/yourname/data"  # Update this path as needed
x_limit = (0,6)  # Example x-axis limit
y_limit = (0,0.5)# Example y-axis limit

# Process each subfolder in the base directory with specified limits
process_subfolders(base_dir, x_limit, y_limit)

#print(merged_df.head())