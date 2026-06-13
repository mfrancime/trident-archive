# A5 Aggregation CLI Tool

This CLI tool processes CSV files containing latitude and longitude coordinates and aggregates them by A5 cell IDs.

## Installation

```bash
npm install
```

## Usage

```bash
node index.js <input.csv> <output.json>
```

### Input Format

The input CSV file should have the following format:
```csv
lng,lat
-0.198465,51.505538
-0.178838,51.491836
-0.205590,51.514910
```

### Output Format

The output JSON file will contain an array of objects, where each object represents an A5 cell and contains:
- `cellId`: The A5 cell identifier
- `center`: The center coordinates of the cell [longitude, latitude]
- `count`: Number of points in this cell
- `points`: Array of all points that fall within this cell

## Example

```bash
node index.js input.csv output.json
``` 