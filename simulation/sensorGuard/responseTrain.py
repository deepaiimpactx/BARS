import random
import requests
import pandas as pd
import threading

# Define the base URL for sending sensor data
base_url = 'http://127.0.0.1:5001/send_sensor_data/train/'

def send_data(client_id, filename):
    # Load the processed data file
    df = pd.read_csv(filename)

    for index, row in df.iterrows():
        data = {
            "sensorId": row['sensorId'],
            "IP_Address": row['IP_Address'],
            "Packet_Rate": row['Packet_Rate'],
            "Packet_Drop_Rate": row['Packet_Drop_Rate'],
            "Packet_Duplication_Rate": row['Packet_Duplication_Rate'],
            "Data_Throughput": row['Data_Throughput'],
            "Signal_Strength": row['Signal_Strength'],
            "SNR": row['SNR'],
            "Battery_Level": row['Battery_Level'],
            "Energy_Consumption_Rate": row['Energy_Consumption_Rate'],
            "Number_of_Neighbors": row['Number_of_Neighbors'],
            "Route_Request_Frequency": row['Route_Request_Frequency'],
            "Route_Reply_Frequency": row['Route_Reply_Frequency'],
            "Data_Transmission_Frequency": row['Data_Transmission_Frequency'],
            "Data_Reception_Frequency": row['Data_Reception_Frequency'],
            "Error_Rate": row['Error_Rate'],
            "CPU_Usage": row['CPU_Usage'],
            "Memory_Usage": row['Memory_Usage'],
            "Bandwidth": row['Bandwidth'],
            "Pinged_IP": row['Pinged_IP'],
            "Is_Malicious": row['Is_Malicious'],
        }

        # Construct the URL with the client_id
        url = base_url + client_id

        # Send POST request with the generated sensor data
        response = requests.post(url, json=data)
        print(response.status_code)
        print(response.json())

def main():
    threads = []
    for client_id in range(1, 6):
        filename = f"../../data/interim/train/data_split_{client_id}.csv"
        thread = threading.Thread(target=send_data, args=(str(client_id), filename))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
