import time
import random
import requests
import threading

# Define the base URL for sending sensor data
base_url = 'http://127.0.0.1:5001/send_sensor_data/'

def generate_random_data():
    ip_address = ".".join(str(random.randint(0, 255)) for _ in range(4))

    # Generate random values for sensor data attributes
    data = {
        "sensorId": random.randint(1, 9999),
        "Packet_Rate": random.randint(80, 120),
        "Packet_Drop_Rate": random.randint(0, 10),
        "Packet_Duplication_Rate": round(random.uniform(0, 0.2), 2),
        "Data_Throughput": random.randint(400, 600),
        "Signal_Strength": random.randint(70, 90),
        "SNR": random.randint(10, 20),
        "Battery_Level": random.randint(30, 50),
        "Energy_Consumption_Rate": random.randint(40, 60),
        "Number_of_Neighbors": random.randint(2, 5),
        "Route_Request_Frequency": random.randint(5, 15),
        "Route_Reply_Frequency": random.randint(5, 15),
        "Data_Transmission_Frequency": random.randint(10, 20),
        "Data_Reception_Frequency": random.randint(10, 20),
        "Error_Rate": round(random.uniform(0, 0.2), 2),
        "CPU_Usage": random.randint(20, 40),
        "Memory_Usage": random.randint(30, 50),
        "Bandwidth": random.randint(100, 200),
        "Pinged_IP": ip_address
    }
    return data

def send_data(client_id):
    # Construct the URL with the client_id
    url = base_url + client_id

    for _ in range(2):
        data = generate_random_data()

        # Send POST request with the generated sensor data
        response = requests.post(url, json=data)
        print(response.status_code)
        print(response.json())
        time.sleep(0)

def main():
    threads = []
    for client_id in range(1, 6):
        thread = threading.Thread(target=send_data, args=(str(client_id),))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
