import pandas as pd
import random

def drop_unnecessary_columns(df):
    # Drops unnecessary columns (e.g., Timestamp, IP_Address, Node_ID)
    df.drop(columns=['Timestamp'], inplace=True)
    return df

def rename_columns(df):
    # Renames Node_ID to sensorId
    df.rename(columns={'Node_ID': 'sensorId'}, inplace=True)
    return df

def add_pinged_ip_column(df):
    # Add a new column 'Pinged_IP' with randomly generated IP addresses
    ip_addresses = ['192.168.1.100', '192.168.1.1', '192.168.1.2', '10.0.0.5']
    pinged_ips = []
    for _ in range(len(df)):
        # Randomly choose whether to use specified IP or random IP
        if random.random() < 0.2:  # Adjust this probability as needed
            pinged_ips.append(random.choice(ip_addresses))
        else:
            pinged_ips.append(f"{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}")
    df['Pinged_IP'] = pinged_ips
    return df

def select_columns(df):
    # Selects specific columns
    selected_columns = [
        "sensorId", "IP_Address", "Packet_Rate", "Packet_Drop_Rate",
        "Packet_Duplication_Rate", "Data_Throughput", "Signal_Strength",
        "SNR", "Battery_Level", "Energy_Consumption_Rate",
        "Number_of_Neighbors", "Route_Request_Frequency",
        "Route_Reply_Frequency", "Data_Transmission_Frequency",
        "Data_Reception_Frequency", "Error_Rate", "CPU_Usage",
        "Memory_Usage", "Bandwidth", "Pinged_IP", "Is_Malicious",
    ]
    return df[selected_columns]

def split_dataset(df):
    # Split dataset into 5 parts
    data_splits = []
    split_size = len(df) // 5
    for i in range(5):
        start_idx = i * split_size
        end_idx = (i + 1) * split_size
        data_splits.append(df.iloc[start_idx:end_idx])
    return data_splits

def main():
    # Load data
    df = pd.read_csv("../../data/raw/data.csv")

    # Drop unnecessary columns
    df = drop_unnecessary_columns(df)

    # Rename Node_ID to sensorId
    df = rename_columns(df)

    # Add Pinged_IP column
    df = add_pinged_ip_column(df)

    # Select specific columns
    df = select_columns(df)

    # Split dataset into 5 parts
    data_splits = split_dataset(df)

    # Save processed data (overwrite the original CSV file)
    for i, data_split in enumerate(data_splits):
        data_split.to_csv(f"../../data/interim/data_split_{i + 1}.csv", index=False)

if __name__ == "__main__":
    main()
