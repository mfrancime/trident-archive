import csv
import json
import sys

def convert_csv_to_coordinates(csv_file):
    coordinates = []
    
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Extract longitude and latitude, converting to float
                lon = float(row['longitude'])
                lat = float(row['latitude'])
                coordinates.append([lon, lat])
            except (ValueError, KeyError) as e:
                print(f"Error processing row: {e}", file=sys.stderr)
                continue
    
    return coordinates

def main():
    if len(sys.argv) != 2:
        print("Usage: python convert.py <input_csv_file>", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    coordinates = convert_csv_to_coordinates(input_file)
    
    # Output the coordinates as JSON
    print(json.dumps(coordinates, indent=2))

if __name__ == "__main__":
    main() 