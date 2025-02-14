# Streamlined Data Pipeline for Real-Time Threat Detection and Model Inference
## BARS Architecture

## Abstract 
Real-time threat detection in streaming data is crucial yet
challenging due to varying data volumes and speeds. This paper presents
an architecture designed to manage large-scale, high-speed data streams
using deep learning and machine learning models. The system utilizes
Apache Kafka for high-throughput data transfer and a publish-subscribe
model to facilitate continuous threat detection. Various machine learning techniques, including XGBoost, Random Forest, and LightGBM, are
evaluated to identify the best model for classification. The ExtraTrees
model achieves exceptional performance with accuracy, precision, recall,
and F1 score all reaching 99\% using the SensorNetGuard dataset within
this architecture. The PyFlink framework, with its parallel processing
capabilities, supports real-time training and adaptation of these models. The system calculates prediction metrics every 2,000 data points,
ensuring efficient and accurate real-time threat detection.

## 🎒 Tech Stack

![Jupyter Notebook](https://img.shields.io/badge/jupyter-%23FA0F00.svg?style=for-the-badge&logo=jupyter&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Apache Flink](https://img.shields.io/badge/Apache%20Flink-E6526F?style=for-the-badge&logo=Apache%20Flink&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-000?style=for-the-badge&logo=apachekafka)
![YAML](https://img.shields.io/badge/yaml-%23ffffff.svg?style=for-the-badge&logo=yaml&logoColor=151515)

## Current Pipeline

![pipeline](./DFD.png "Pipeline")


## 🖥️ Run Locally

Clone the project

```bash
  git clone https://github.com/deepaiimpactx/BARS
```

Go to the project directory

```bash
  cd BARS
```

Build the images
```bash
  docker-compose build
```

Start docker container
```bash
  docker compose up -d   
```

### Other Useful commands

Check kafka messages
```shell
docker exec -it broker kafka-console-consumer --bootstrap-server localhost:9092 --topic output_topic --partition 0 --offset 4990 --max-messages 20
```

To run a pyflink job
```shell
docker-compose exec flink-jobmanager flink run -py /opt/flink/usr_jobs/classifier.py
```

### To verify database records

#### PostgreSQL

Connect to the PostgreSQL Container:

```sh
docker exec -it postgres bash
```

Use psql to Query the Database:
Once inside the container, use the psql command-line tool to connect to your PostgreSQL database:

```sh
psql -U postgres -d postgres
```

Run SQL queries to check the data in your tables:
```sql
\dt     -- List all tables
SELECT * FROM sensor_data;
```

Project Organization
------------

    .
    ├── academicPapers  <- Research paper
    ├── dash    <- Flask app for DL feature selection
    │   ├── uploads
    ├── data    <- Directory for datasets organized by their processing stages
    │   ├── external    <- Data from external sources
    │   ├── interim     <- Intermediate, transformed data
    │   │   ├── pred    <- prediction data
    │   │   ├── train   <- training data
    │   ├── processed   <- Cleaned and final data ready for modeling or analysis
    │   └── raw         <- Raw, unprocessed data
    ├── initdb      <- Database initialization scripts for Postgres
    ├── kafka       <- Kafka-related scripts and services
    │   ├── api
    │   ├── consumer
    ├── notebooks       <- Jupyter notebooks for data exploration and analysis
    ├── pyflink     <- Directory for Flink in Python
    │   ├── saved_models    <- Directory for pickle serialised ML models saved from PyFLink jobs. Acts as a shared directory for PyFLink Job&Task manager.
    │   ├── usr_jobs        <- Directory for Python scripts to be submitted to Flink 
    ├── simulation      <- Directory for simulating batch and stream environments
    │   └── sensorGuard     <- SensorNetGuard Dataset
    ├── src     <- Source code directory
    │   ├── data    <- Scripts for data handling and processing
    │   ├── features    <- Scripts for feature engineering
    │   ├── models      <- Scripts related to model training and predictions
    │   ├── visualization   <- Scripts for data visualization
    ├── uploads
    ├── LICENSE     <- Project license file
    ├── Makefile    <- Makefile for build commands 
    ├── README.md   <- Top-level README for developers using this project
    ├── docker-compose.yml      <- Docker Compose configuration for multi-container application
    ├── qodana.yaml     <- Configuration file for Qodana- code quality and inspection tool
    └── requirements.txt    <- Python dependencies for the project


--------

<p><small>Project structure based on the <a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project template</a></small></p>

<p><small>Generate fresh structure with</small></p>
<small>

```
tree -L 3 --dirsfirst
```
</small>


## 👨‍💻 Authors

[![Static Badge](https://img.shields.io/badge/sankbphc-green?logo=GitHub&link=https%3A%2F%2Fgithub.com%2Fsankbphc)
](https://www.github.com/sankbphc)
[![Static Badge](https://img.shields.io/badge/Rajkanwars15-yellow?logo=GitHub&link=https%3A%2F%2Fgithub.com%2FRajkanwars15)
](https://www.github.com/rajkanwars15)
[![Static Badge](https://img.shields.io/badge/aravindan2-red?logo=GitHub&link=https%3A%2F%2Fgithub.com%2Faravindan2)
](https://www.github.com/aravindan2)
