from flask import Flask, request, redirect, url_for, flash, render_template_string
from werkzeug.utils import secure_filename
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import lightgbm as lgb
from zoofs import ParticleSwarmOptimization, GeneticOptimization
from confluent_kafka import Producer
import pyswarm
import json
import numpy as np
from keras.models import Sequential
from keras.layers import Dense, Dropout, LSTM, Input
from keras.optimizers import Adam
from sklearn.preprocessing import StandardScaler
from pyswarm import pso

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
app.secret_key = 'supersecretkey'

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def preprocess_data(file_path, target_column):
    data = pd.read_csv(file_path)
    X = data.drop(target_column, axis=1)
    y = data[target_column]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    return X_scaled, y, X.columns.tolist()

def create_autoencoder(input_dim, encoding_dim):
    input_layer = Input(shape=(input_dim,))
    encoder = Dense(encoding_dim, activation="relu")(input_layer)
    decoder = Dense(input_dim, activation="sigmoid")(encoder)
    autoencoder = Sequential([input_layer, encoder, decoder])
    autoencoder.compile(optimizer='adam', loss='mean_squared_error')
    return autoencoder, encoder

def train_autoencoder(autoencoder, X_train, epochs=5, batch_size=256):
    autoencoder.fit(X_train, X_train, epochs=epochs, batch_size=batch_size, shuffle=True, validation_split=0.2)

def extract_features(encoder, X):
    return encoder.predict(X)

def create_lstm_model(input_shape):
    model = Sequential()
    model.add(LSTM(units=64, return_sequences=True, input_shape=input_shape))
    model.add(LSTM(units=32))
    model.add(Dense(units=1, activation='sigmoid'))
    model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    return model

def create_dnn_model(input_dim):
    model = Sequential()
    model.add(Dense(128, input_dim=input_dim, activation='relu'))
    model.add(Dropout(0.5))
    model.add(Dense(64, activation='relu'))
    model.add(Dropout(0.5))
    model.add(Dense(32, activation='relu'))
    model.add(Dense(1, activation='sigmoid'))
    model.compile(optimizer=Adam(lr=0.001), loss='binary_crossentropy', metrics=['accuracy'])
    return model

def send_to_kafka(results):
    producer = Producer({'bootstrap.servers': 'broker:29092'})
    topic = 'optimization_results'
    producer.produce(topic, json.dumps(results))
    producer.flush()

# PSO and GA Optimization functions
def run_pso(X_train, y_train, X_valid, y_valid):
    lgb_model = lgb.LGBMRegressor()
    algo_object = ParticleSwarmOptimization(objective_function_topass, n_iteration=20, population_size=20, minimize=True)
    optimized_params = algo_object.fit(lgb_model, X_train, y_train, X_valid, y_valid)
    return optimized_params

def run_ga(X_train, y_train, X_valid, y_valid):
    lgb_model = lgb.LGBMRegressor()
    algo_object = GeneticOptimization(objective_function_topass, n_iteration=20, population_size=20, selective_pressure=2, elitism=2, mutation_rate=0.05, minimize=True)
    optimized_params = algo_object.fit(lgb_model, X_train, y_train, X_valid, y_valid)
    return optimized_params

def train_and_evaluate(X_train, X_valid, y_train, y_valid, selected_features):
    X_train_selected = X_train[selected_features]
    X_valid_selected = X_valid[selected_features]
    optimized_model = lgb.LGBMRegressor()
    optimized_model.set_params(force_col_wise=True, verbose=-1)
    optimized_model.fit(X_train_selected, y_train)
    y_pred = optimized_model.predict(X_valid_selected)
    mse = mean_squared_error(y_valid, y_pred)
    return selected_features, mse

def objective_function_topass(model, X_train, y_train, X_valid, y_valid):
    model.set_params(force_col_wise=True, verbose=-1)
    model.fit(X_train, y_train)
    return mean_squared_error(y_valid, model.predict(X_valid))

# Routes
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            df = pd.read_csv(file_path)
            columns = df.columns.tolist()
            return render_template_string('''
            <!doctype html>
            <title>Select Target Variable</title>
            <h1>Select Target Variable</h1>
            <form method="post" action="/select_target">
              <input type="hidden" name="file_path" value="{{ file_path }}">
              <label for="target">Choose a target variable:</label>
              <select name="target" id="target">
                {% for column in columns %}
                  <option value="{{ column }}">{{ column }}</option>
                {% endfor %}
              </select>
              <input type="submit" value="Submit">
            </form>
            ''', columns=columns, file_path=file_path)
    return '''
    <!doctype html>
    <title>Upload a CSV File</title>
    <h1>Upload a CSV File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

@app.route('/select_target', methods=['POST'])
def select_target():
    file_path = request.form['file_path']
    target = request.form['target']
    df = pd.read_csv(file_path)
    X = df.drop(columns=[target])
    y = df[target]
    X_train, X_valid, y_train, y_valid = train_test_split(X, y, test_size=0.2, random_state=42)

    # Run Particle Swarm Optimization
    pso_features = run_pso(X_train, y_train, X_valid, y_valid)
    pso_results = train_and_evaluate(X_train, X_valid, y_train, y_valid, pso_features)

    # Run Genetic Algorithm Optimization
    ga_features = run_ga(X_train, y_train, X_valid, y_valid)
    ga_results = train_and_evaluate(X_train, X_valid, y_train, y_valid, ga_features)

    # Preprocess data for Autoencoder and LSTM
    X_scaled, y, feature_names = preprocess_data(file_path, target)
    X_train_scaled, X_valid_scaled, y_train_scaled, y_valid_scaled = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    # Autoencoder
    input_dim = X_train_scaled.shape[1]
    encoding_dim = int(input_dim / 2)
    autoencoder, encoder = create_autoencoder(input_dim, encoding_dim)
    train_autoencoder(autoencoder, X_train_scaled)
    autoencoder_features = extract_features(encoder, X_valid_scaled)

    # LSTM
    time_steps = 1
    features = X_train.shape[1]
    input_shape = (time_steps, features)
    X_train_lstm = np.reshape(X_train, (X_train.shape[0], time_steps, features))
    X_valid_lstm = np.reshape(X_valid, (X_valid.shape[0], time_steps, features))
    lstm_model = create_lstm_model(input_shape)
    lstm_model.fit(X_train_lstm, y_train, epochs=3, batch_size=32)
    lstm_features = lstm_model.predict(X_valid_lstm)

    # DNN
    dnn_model = create_dnn_model(input_dim)
    dnn_model.fit(X_train_scaled, y_train, epochs=10, batch_size=32, validation_split=0.2)
    dnn_features = dnn_model.predict(X_valid_scaled)

    # Collect all results
    results = {
        'pso': {
            'features': pso_results[0],
            'mse': pso_results[1]
        },
        'ga': {
            'features': ga_results[0],
            'mse': ga_results[1]
        },
        'autoencoder': {
            'features': autoencoder_features.tolist(),
            'mse': mean_squared_error(y_valid_scaled, autoencoder_features)
        },
        'lstm': {
            'features': lstm_features.tolist(),
            'mse': mean_squared_error(y_valid, lstm_features)
        },
        'dnn': {
            'features': dnn_features.tolist(),
            'mse': mean_squared_error(y_valid_scaled, dnn_features)
        }
    }

    # Send results to Kafka
    send_to_kafka(results)

    # Display results
    return render_template_string('''
    <!doctype html>
    <title>Results</title>
    <h1>Results</h1>
    <h2>Particle Swarm Optimization (PSO)</h2>
    <p>Selected Features: {{ pso_features }}</p>
    <p>Mean Squared Error (MSE): {{ pso_mse }}</p>
    <h2>Genetic Algorithm (GA)</h2>
    <p>Selected Features: {{ ga_features }}</p>
    <p>Mean Squared Error (MSE): {{ ga_mse }}</p>
    <h2>Autoencoder</h2>
    <p>Selected Features: {{ autoencoder_features }}</p>
    <p>Mean Squared Error (MSE): {{ autoencoder_mse }}</p>
    <h2>LSTM</h2>
    <p>Selected Features: {{ lstm_features }}</p>
    <p>Mean Squared Error (MSE): {{ lstm_mse }}</p>
    <h2>DNN</h2>
    <p>Selected Features: {{ dnn_features }}</p>
    <p>Mean Squared Error (MSE): {{ dnn_mse }}</p>
    ''', pso_features=results['pso']['features'], pso_mse=results['pso']['mse'],
         ga_features=results['ga']['features'], ga_mse=results['ga']['mse'],
         autoencoder_features=results['autoencoder']['features'], autoencoder_mse=results['autoencoder']['mse'],
         lstm_features=results['lstm']['features'], lstm_mse=results['lstm']['mse'],
         dnn_features=results['dnn']['features'], dnn_mse=results['dnn']['mse'])

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, host='0.0.0.0')
