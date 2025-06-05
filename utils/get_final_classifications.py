import csv
from db import access
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def export_summary_to_csv(output_path="final_classification/classification_summary.csv"):
    db = access.DBAccess()
    rows = db.get_final_classifications_with_metadata()

    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["video_id", "final_classification", "features", "username","description","music_id"])
        for row in rows:
            writer.writerow([
                row.video_id,
                row.final_classification,
                row.features,
                row.username,
                row.description,
                row.music_id
            ])

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
    plt.savefig("final_classification/classification_bar_chart.png")
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

def get_users_classification_map():
    db = access.DBAccess()
    user_map, user_totals, total_map = db.get_classification_map_by_user()

    # Convert to DataFrame
    class_labels = sorted({cls for counts in user_map.values() for cls in counts})

    data = []
    total_class_counts = {cls: 0 for cls in class_labels}
    grand_total = sum(user_totals.values())

    for i, (username, counts) in enumerate(user_map.items()):
        row = {'User': f'User {i + 1}'}
        total = user_totals[username]
        for cls in class_labels:
            count = counts.get(cls, 0)
            row[cls] = count
            total_class_counts[cls] += count
        row['Total'] = total
        data.append(row)

    avg_row = {'User': 'Average'}
    for cls in class_labels:
        avg_row[cls] = total_class_counts[cls]
    avg_row['Total'] = grand_total
    data.append(avg_row)

    df = pd.DataFrame(data)

    # Normalize for percentages (used for bar height)
    df_percent = df.copy()
    for cls in class_labels:
        df_percent[cls] = df_percent[cls] / df_percent['Total'] * 100

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    bottom = [0] * len(df)

    for cls in class_labels:
        values = df_percent[cls]
        bar = ax.bar(df['User'], values, bottom=bottom, label=cls)

        # Add count and percent labels
        for i, (val, percent) in enumerate(zip(df[cls], values)):
            if val > 0:
                ax.text(i, bottom[i] + values[i] / 2,
                        f"{val} ({percent:.1f}%)",
                        ha='center', va='center', fontsize=8, color='white')
        bottom = [b + p for b, p in zip(bottom, values)]

    ax.set_ylabel("Percentage")
    ax.set_title("Classification Distribution per User")
    ax.legend(title="Classification", loc='lower center',bbox_to_anchor=(0.5, -0.3),ncol=len(class_labels))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("final_classification/classification_map_users.png")
    plt.close()


if __name__ == "__main__":
    export_summary_to_csv()
    # Load the CSV
    df = pd.read_csv("final_classification/classification_summary.csv")
    plot_bar_chart(df)
    plot_feature_distribution_for_classification(df, "Hamas", output_path="final_classification/features_hamas.png")
    plot_feature_distribution_for_classification(df, "Fatah", output_path="final_classification/features_fatah.png")
    get_users_classification_map()
