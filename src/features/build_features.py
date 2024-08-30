import pandas as pd

def drop_unnecessary_columns(df):
    # Drops unnecessary columns (e.g., Timestamp, IP_Address, Node_ID)
    df.drop(columns=['Timestamp', 'IP_Address', 'Node_ID'], inplace=True)
    return df

def get_feature_names(df):
    # Gets a list of feature names after dropping columns
    return df.columns


def main():
    # Load data
    df = pd.read_csv("../../data/raw/data.csv")

    # Drop unnecessary columns
    df = drop_unnecessary_columns(df)

    # Get feature names
    feature_names = get_feature_names(df)

    # Save processed data (overwrite the original CSV file)
    df.to_csv("../../data/processed/data.csv", index=False)

if __name__ == "__main__":
    main()
