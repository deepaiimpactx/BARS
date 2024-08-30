# src/features/feature_selection.py

from src.features.feature_selection_functions import *

# Load your dataset
df = pd.read_csv("../../data/processed/data.csv")

X = df.drop(columns=['Is_Malicious'])
feature_names = X.columns
y = df['Is_Malicious']

# Univariate Feature Selection
selected_features_kbest = select_k_best(X, y, feature_names)
selected_features_percentile = select_percentile(X, y, feature_names)

# Correlation-based Feature Selection
selected_features_correlation = correlation_based(X, df)
selected_features_Pcorrelation = pearson_correlation(X, df)

# Elastic Net
selected_features_elasticNet = elastic_net(X, y)

# Wrapper Methods
selected_features_rfe, selected_features_fwd, selected_features_bkd = wrapper_methods(X, y)

# Tree-based Feature Selection
selected_features, selected_features_rf, selected_features_gb = tree_based(X, y)

# XGBoost
selected_features_xgb = xgboost_based(X, y)

# Results
feature_selection_results = {
    'Select K Best': selected_features_kbest,
    'Select Percentile': selected_features_percentile,
    'Correlation Based': selected_features_correlation,
    'Pearson Correlation': selected_features_Pcorrelation,
    'Elastic Net': selected_features_elasticNet,
    'Recursive Feature Elimination': selected_features_rfe,
    'Forward Selection': selected_features_fwd,
    'Backward Elimination': selected_features_bkd,
    'Random Forest': selected_features_rf,
    'Gradient Boosting': selected_features_gb,
    'XGBoost': selected_features_xgb,
    'Manual': ['Packet_Drop_Rate', 'Energy_Consumption_Rate', 'Error_Rate']
}

print(feature_selection_results)
