from flask import Flask, request, redirect, url_for, flash, render_template_string
from werkzeug.utils import secure_filename
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import lightgbm as lgb
from zoofs import ParticleSwarmOptimization, GeneticOptimization
from confluent_kafka import Producer
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}
app.secret_key = 'supersecretkey'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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

    # Store results in dictionaries
    results = {
        'pso': {
            'features': pso_results[0],
            'mse': pso_results[1]
        },
        'ga': {
            'features': ga_results[0],
            'mse': ga_results[1]
        }
    }

    # Send results to Kafka
    send_to_kafka(results)

    return render_template_string('''
    <!doctype html>
    <title>Optimization Results</title>
    <h1>Optimization Results</h1>
    <h2>Particle Swarm Optimization (PSO)</h2>
    <p>Features: {{ pso_features }}</p>
    <p>Mean Squared Error (MSE): {{ pso_mse }}</p>
    <h2>Genetic Algorithm (GA)</h2>
    <p>Features: {{ ga_features }}</p>
    <p>Mean Squared Error (MSE): {{ ga_mse }}</p>
    ''', pso_features=results['pso']['features'], pso_mse=results['pso']['mse'],
         ga_features=results['ga']['features'], ga_mse=results['ga']['mse'])

def run_pso(X_train, y_train, X_valid, y_valid):
    lgb_model = lgb.LGBMRegressor()
    algo_object = ParticleSwarmOptimization(objective_function_topass, n_iteration=20,
                                            population_size=20, minimize=True)
    optimized_params = algo_object.fit(lgb_model, X_train, y_train, X_valid, y_valid)
    return optimized_params

def run_ga(X_train, y_train, X_valid, y_valid):
    lgb_model = lgb.LGBMRegressor()
    algo_object = GeneticOptimization(objective_function_topass, n_iteration=20,
                                      population_size=20, selective_pressure=2, elitism=2,
                                      mutation_rate=0.05, minimize=True)
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

def send_to_kafka(results):
    producer = Producer({'bootstrap.servers': 'broker:29092'})
    topic = 'optimization_results'
    
    producer.produce(topic, json.dumps(results))
    producer.flush()

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, host='0.0.0.0')
