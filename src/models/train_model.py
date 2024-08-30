import pandas as pd
import numpy as np
import lightgbm as lgb
import pickle
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from src.features.feature_selection import feature_selection_results


def train_lightgbm(X_train, y_train, X_test, y_test):
    # Select features based on feature selection results
    selected_features = feature_selection_results['Correlation Based']

    # Prepare data for LightGBM
    lgb_train = lgb.Dataset(X_train[selected_features], y_train)
    lgb_eval = lgb.Dataset(X_test[selected_features], y_test, reference=lgb_train)

    # Set parameters
    params = {
        'boosting_type': 'gbdt',
        'objective': 'binary',
        'metric': 'binary_error',  # binary classification error
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': 0
    }

    # Train the model
    model = lgb.train(params,
                      lgb_train,
                      num_boost_round=100)

    # Save the model using pickle
    with open("../../models/trained_model.pkl", "wb") as f:
        pickle.dump(model, f)

    # Predict on test set
    y_pred = model.predict(X_test[selected_features])
    y_pred_binary = np.round(y_pred)  # Convert probabilities to binary predictions (0 or 1)

    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred_binary)
    precision = precision_score(y_test, y_pred_binary)
    recall = recall_score(y_test, y_pred_binary)
    f1 = f1_score(y_test, y_pred_binary)

    # Print metrics
    print("Accuracy:", accuracy)
    print("Precision:", precision)
    print("Recall:", recall)
    print("F1 Score:", f1)


def main():
    # Load preprocessed data
    df = pd.read_csv("../../data/processed/data.csv")

    # Split data into train and test sets
    X = df.drop(columns=['Is_Malicious'])
    y = df['Is_Malicious']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    # Train LightGBM model and print metrics
    train_lightgbm(X_train, y_train, X_test, y_test)


if __name__ == "__main__":
    main()
