import csv
import json
import sys
import os

def convert_csv_to_json(csv_file_path, output_json_path):
    """
    Converts a LifePath/Background CSV to JSON using only Python standard libraries.
    Automatically skips empty columns/cells and handles nested structures.
    """
    if not os.path.exists(csv_file_path):
        print(f"Error: The file '{csv_file_path}' was not found.")
        return

    json_data = []
    
    # 'utf-8-sig' handles the BOM (Byte Order Mark) from Excel exports
    with open(csv_file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            entry = {}
            for col, val in row.items():
                # --- Skip empty columns/cells ---
                if val is None:
                    continue
                val = val.strip()
                if val == "":
                    continue
                
                # Handle nested keys using the '/' delimiter
                if '/' in col:
                    prefix, subkey = col.split('/', 1)
                    
                    # 1. Handle Lists (headers like 'UnlockedBackgrounds/0')
                    if subkey.isdigit():
                        if prefix not in entry:
                            entry[prefix] = []
                        entry[prefix].append(val)
                    
                    # 2. Handle Nested Dictionaries (headers like 'AttributeModifiers/Key')
                    else:
                        if prefix not in entry:
                            entry[prefix] = {}
                        
                        try:
                            # Convert to float for numeric modifiers (e.g., 20.0)
                            entry[prefix][subkey] = float(val)
                        except (ValueError, TypeError):
                            # Keep as string if it's not a number
                            entry[prefix][subkey] = val
                else:
                    # 3. Handle standard top-level fields
                    entry[col] = val
            
            # Formatting: Ensure 'Description' appears at the end of the entry if it exists
            if 'Description' in entry:
                description = entry.pop('Description')
                entry['Description'] = description
                
            json_data.append(entry)
            
    # Save to JSON file
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"Success! Processed {len(json_data)} rows.")
    print(f"Output saved to: {output_json_path}")

# Command-line Execution
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 backgroundCSVtoJSON.py input.csv output.json")
    else:
        input_csv = sys.argv[1]
        output_json = sys.argv[2]
        convert_csv_to_json(input_csv, output_json)