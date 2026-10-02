import csv
import json

def convert_vertical_csv_to_json(csv_filepath, json_filepath):
    all_topics = []

    with open(csv_filepath, mode='r', encoding='utf-8') as csv_file:
        # Read all rows into a list to allow column-based iteration
        rows = list(csv.reader(csv_file))
        if not rows:
            return

        header = rows[0]
        # Iterate through the header 3 columns at a time
        for col_index in range(0, len(header), 3):
            
            # Now go down the rows for this specific column triplet
            # We start from index 1 to skip the header row
            for row_index in range(1, len(rows)):
                row = rows[row_index]
                
                # Ensure the row actually has these columns
                if col_index >= len(row):
                    continue
                
                raw_name = row[col_index].strip()
                
                # Skip if the Name cell is empty
                if not raw_name:
                    continue

                # Prepend the prefix
                formatted_name = f"Bronze.Topic.{raw_name}" if not raw_name.startswith("Bronze.Topic.") else raw_name
                
                # Grab Description (Name + 1)
                description = ""
                if col_index + 1 < len(row):
                    description = row[col_index + 1].strip()

                # Build the entry
                topic_entry = {
                    "Name": formatted_name,
                    "Tag": formatted_name,
                    "DevComment": description
                }

                # Handle the Ignore field (Name + 2)
                if col_index + 2 < len(row):
                    ignore_val = row[col_index + 2].strip().upper()
                    if ignore_val == 'TRUE':
                        topic_entry["Ignore"] = True

                all_topics.append(topic_entry)

    # Export to JSON
    with open(json_filepath, mode='w', encoding='utf-8') as json_file:
        json.dump(all_topics, json_file, indent=4)
    
    print(f"Successfully processed vertical blocks and exported {len(all_topics)} topics.")

if __name__ == "__main__":
    input_csv = 'DialogueTopicsList.csv'
    output_json = 'Topic.json'
    convert_vertical_csv_to_json(input_csv, output_json)