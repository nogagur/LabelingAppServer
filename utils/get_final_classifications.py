import csv
from db import access
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def export_summary_to_csv(output_path="classification_summary.csv"):
    db = access.DBAccess()
    rows = db.get_final_classifications_with_features()

    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["video_id", "final_classification", "features"])
        for row in rows:
            writer.writerow([row.video_id, row.final_classification, row.features])

    print(f"Exported to {output_path}")

def plot_bar_chart(df):
    plt.figure(figsize=(8, 5))
    ax = sns.countplot(data=df, x='final_classification', order=df['final_classification'].value_counts().index)
    plt.title("Number of Videos by Final Classification")
    plt.xlabel("Classification")
    plt.ylabel("Count")
    plt.xticks(rotation=45)

    # Add value labels on top of each bar
    for p in ax.patches:
        count = int(p.get_height())
        ax.annotate(f'{count}',
                    (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='bottom',
                    fontsize=10)

    plt.tight_layout()
    plt.savefig("classification_bar_chart.png")
    plt.close()

def plot_feature_distribution_for_classification(df, classification_label, output_path=None):
    """
    Plots a bar chart showing the top N feature counts for a given classification.

    Parameters:
        df (pd.DataFrame): The full classification summary dataframe
        classification_label (str): e.g., 'Hamas', 'Fatah'
        output_path (str): Optional path to save the image
    """
    # Filter by classification
    df_filtered = df[df['final_classification'] == classification_label].copy()
    df_filtered['features'] = df_filtered['features'].fillna('')
    df_filtered = df_filtered.assign(feature=df_filtered['features'].str.split(', ')).explode('feature')

    # Count features
    feature_counts = df_filtered['feature'].value_counts()

    if feature_counts.empty:
        print(f"No features found for classification: {classification_label}")
        return

    # Plot
    plt.figure(figsize=(10, 5))
    ax = feature_counts.plot(kind='bar')
    plt.title(f"Features in '{classification_label}' Classifications")
    plt.xlabel("Feature")
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Add count labels
    for i, v in enumerate(feature_counts):
        ax.text(i, v + 1, str(v), ha='center', va='bottom', fontsize=9)

    # Save or show
    if output_path:
        plt.savefig(output_path)
    else:
        plt.show()

    plt.close()


if __name__ == "__main__":
    export_summary_to_csv()
    # Load the CSV
    df = pd.read_csv("classification_summary.csv")
    plot_bar_chart(df)
    plot_feature_distribution_for_classification(df, "Hamas", output_path="features_hamas.png")
    plot_feature_distribution_for_classification(df, "Fatah", output_path="features_fatah.png")
