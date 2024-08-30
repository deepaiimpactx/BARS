from src.common import *


def select_k_best(X, y, feature_names):
    k_best = SelectKBest(score_func=f_classif, k=5)
    X_kbest = k_best.fit_transform(X, y)
    k_best_indices = np.where(k_best.get_support())[0]
    selected_features_kbest = [feature_names[i] for i in k_best_indices]
    return selected_features_kbest


def select_percentile(X, y, feature_names):
    X_non_negative = X - np.min(X) + 1e-6
    percentile = SelectPercentile(score_func=chi2, percentile=25)
    X_percentile = percentile.fit_transform(X_non_negative, y)
    percentile_indices = np.where(percentile.get_support())[0]
    selected_features_percentile = feature_names[percentile_indices]
    return selected_features_percentile


def correlation_based(X, df):
    correlation_matrix = df.corr()
    correlation_with_target = correlation_matrix.iloc[:-1, -1].abs()
    correlation_with_target_sorted = correlation_with_target.sort_values(ascending=False)
    k = 5
    selected_features_correlation = correlation_with_target_sorted.head(k).index.tolist()
    return selected_features_correlation


def pearson_correlation(X, df):
    pearson_corr_matrix = df.corr(method='pearson')
    Pcorrelation_with_target = pearson_corr_matrix.iloc[:-1, -1].abs()
    Pcorrelation_with_target_sorted = Pcorrelation_with_target.sort_values(ascending=False)
    k = 5
    selected_features_Pcorrelation = Pcorrelation_with_target_sorted.head(k).index.tolist()
    return selected_features_Pcorrelation


def elastic_net(X, y, threshold=0.05):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    elasticnet = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
    elasticnet.fit(X_train_scaled, y_train)
    y_pred = elasticnet.predict(X_test_scaled)
    mse = mean_squared_error(y_test, y_pred)
    selected_features_elasticNet = X.columns[np.abs(elasticnet.coef_) > threshold]
    return selected_features_elasticNet


def wrapper_methods(X, y, num_features_to_select=5):
    model = LinearRegression()

    # Recursive Feature Elimination (RFE)
    rfe = RFE(estimator=model, n_features_to_select=num_features_to_select)
    rfe.fit(X, y)
    selected_features_rfe = X.columns[rfe.support_]

    # Forward Selection
    sfs = SequentialFeatureSelector(estimator=model, n_features_to_select=num_features_to_select,
                                    direction='forward', scoring='r2')
    sfs.fit(X, y)
    selected_features_fwd = X.columns[sfs.get_support()]

    # Backward Elimination
    sfs = SequentialFeatureSelector(estimator=model, n_features_to_select=num_features_to_select,
                                    direction='backward', scoring='r2')
    sfs.fit(X, y)
    selected_features_bkd = X.columns[sfs.get_support()]

    return selected_features_rfe, selected_features_fwd, selected_features_bkd


def tree_based(X, y, threshold=0.05):
    # Decision Tree
    clf = DecisionTreeClassifier()
    clf.fit(X, y)
    feature_importances = clf.feature_importances_
    selected_features = X.columns[feature_importances > threshold]

    # Random Forest
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)
    feature_importances = clf.feature_importances_
    selected_features_rf = X.columns[feature_importances > threshold]

    # Gradient Boosting
    clf = GradientBoostingClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)
    feature_importances = clf.feature_importances_
    selected_features_gb = X.columns[feature_importances > threshold]

    return selected_features, selected_features_rf, selected_features_gb


def xgboost_based(X, y, threshold=0.05):
    dtrain = xgb.DMatrix(X, label=y)
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'seed': 42
    }
    num_boost_round = 100
    bst = xgb.train(params, dtrain, num_boost_round)
    importance = bst.get_score(importance_type='weight')
    selected_features_xgb = [feat for feat, score in importance.items() if score > threshold]
    return selected_features_xgb
