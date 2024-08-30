
from flask import Flask, request, redirect, url_for, flash, render_template_string
from werkzeug.utils import secure_filename
import os
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, accuracy_score
from sklearn.ensemble import RandomForestClassifier
import lightgbm as lgb
from zoofs import ParticleSwarmOptimization, GeneticOptimization
from confluent_kafka import Producer
import json
import numpy as np
from keras.models import Sequential
from keras.layers import Dense, Dropout, LSTM, Input
from keras.optimizers import Adam
from sklearn.preprocessing import StandardScaler
from pyswarm import pso
from threading import Thread

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
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def send_to_kafka(results, topic):
    producer = Producer({'bootstrap.servers': 'broker:29092'})
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
    accuracy = accuracy_score(y_valid, np.round(y_pred))
    print(f'Selected Features: {selected_features}')
    print(f'Mean Squared Error: {mse}')
    print(f'Accuracy: {accuracy}')
    return selected_features, mse, accuracy

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

    # Run tasks in parallel
    Thread(target=run_pso_task, args=(X_train, y_train, X_valid, y_valid)).start()
    Thread(target=run_ga_task, args=(X_train, y_train, X_valid, y_valid)).start()
    Thread(target=run_lstm_task, args=(X_train, y_train, X_valid, y_valid, file_path, target)).start()
    Thread(target=run_dnn_task, args=(file_path, target)).start()

    return render_template_string('''
    <!doctype html>
    <title>Processing</title>
    <h1>Processing...</h1>
    <p>Results will be sent to Kafka shortly.</p>
    ''')

# Separate tasks
def run_pso_task(X_train, y_train, X_valid, y_valid):
    pso_features = run_pso(X_train, y_train, X_valid, y_valid)
    pso_results = train_and_evaluate(X_train, X_valid, y_train, y_valid, pso_features)
    results = {
        'features': pso_results[0],
        'mse': pso_results[1],
        'accuracy': pso_results[2]
    }
    print(f'PSO Results: {results}')
    send_to_kafka(results, 'pso_optimization_results')

def run_ga_task(X_train, y_train, X_valid, y_valid):
    ga_features = run_ga(X_train, y_train, X_valid, y_valid)
    ga_results = train_and_evaluate(X_train, X_valid, y_train, y_valid, ga_features)
    results = {
        'features': ga_results[0],
        'mse': ga_results[1],
        'accuracy': ga_results[2]
    }
    print(f'GA Results: {results}')
    send_to_kafka(results, 'ga_optimization_results')

def run_lstm_task(X_train, y_train, X_valid, y_valid, file_path, target):
    X_scaled, y, feature_names = preprocess_data(file_path, target)
    time_steps = 1
    features = X_train.shape[1]
    input_shape = (time_steps, features)
    X_train_lstm = np.reshape(X_train, (X_train.shape[0], time_steps, features))
    X_valid_lstm = np.reshape(X_valid, (X_valid.shape[0], time_steps, features))
    lstm_model = create_lstm_model(input_shape)
    lstm_model.fit(X_train_lstm, y_train, epochs=3, batch_size=32)

    # Feature Extraction
    feature_extractor = Sequential()
    feature_extractor.add(lstm_model.layers[0])
    feature_extractor.add(lstm_model.layers[1])

    extracted_features = feature_extractor.predict(X_valid_lstm)

    def objective_function(x):
        selected_features = extracted_features[:, x > 0.5]
        if selected_features.shape[1] == 0:
            return np.inf  # Prevent zero-feature selection
        accuracy = np.mean(selected_features)  # Placeholder for actual evaluation
        return -accuracy

    num_particles = 30
    dimensions = extracted_features.shape[1]

    lb = [0] * dimensions
    ub = [1] * dimensions

    best_solution, best_fitness = pso(objective_function, lb, ub, swarmsize=num_particles, maxiter=100)

    selected_feature_names = [feature_names[i] for i in range(len(feature_names)) if best_solution[i] > 0.5]

    lstm_features = lstm_model.predict(X_valid_lstm)

    results = {
        'features': selected_feature_names,
        'accuracy': accuracy_score(y_valid, np.round(lstm_features))
    }
    print(f'LSTM Results: {results}')
    send_to_kafka(results, 'lstm_results')

def run_dnn_task(file_path, target):
    X_scaled, y, feature_names = preprocess_data(file_path, target)
    X_train_scaled, X_valid_scaled, y_train_scaled, y_valid_scaled = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    input_dim = X_train_scaled.shape[1]
    dnn_model = create_dnn_model(input_dim)
    dnn_model.fit(X_train_scaled, y_train_scaled, epochs=10, batch_size=32, validation_split=0.2)
    
    feature_extractor = Sequential(dnn_model.layers[:-1])  # Remove the last layer
    features = feature_extractor.predict(X_scaled)

    selected_features = features[:, :10]
    clf = RandomForestClassifier()
    scores = cross_val_score(clf, selected_features, y, cv=5)
    print(f"Cross-validation scores using the first 10 features: {scores}")
    print(f"Mean score: {scores.mean()}")

    def fitness_function(feature_indices):
        feature_indices = np.round(feature_indices).astype(int)  # Ensure binary values
        selected_features = features[:, feature_indices == 1]

        if selected_features.shape[1] == 0:
            return float('inf')

        try:
            clf = RandomForestClassifier()
            scores = cross_val_score(clf, selected_features, y, cv=3)
            mean_score = -scores.mean()
            print(f"Features selected: {np.sum(feature_indices)} - Mean CV Score: {mean_score}")
            return mean_score
        except Exception as e:
            print(f"Error during cross-validation: {e}")
            return float('inf')

    lb = [0] * features.shape[1]
    ub = [1] * features.shape[1]

    xopt, fopt = pso(fitness_function, lb, ub, swarmsize=10, maxiter=2)

    selected_features_indices = np.where(np.round(xopt) == 1)[0]
    original_columns = feature_names

    selected_features = [original_columns[i] for i in selected_features_indices if i < len(original_columns)]
    print(f'Optimal features: {selected_features}')

    results = {
        'features': selected_features,
        'accuracy': scores.mean()
    }
    print(f'DNN Results: {results}')
    send_to_kafka(results, 'dnn_results')

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, host='0.0.0.0')
