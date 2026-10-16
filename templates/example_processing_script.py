#!/usr/bin/env python3
"""
Example processing script for electrochemical data.

This script is sent via email with [RUN] in the subject line.
The processor will save this script and execute it with the data directory as an argument.

Usage in email:
- Subject: [RUN] Process cyclic voltammetry data
- Body: 
    Recipients: user@example.com
    data_file: CV_2024_01_01.csv
    analysis_type: peak_detection
    
- Attachment: this script file

The script will:
1. Load electrochemical data from the specified file
2. Perform the requested analysis
3. Save results (graphs, CSVs) to the same directory
"""

import argparse
import csv
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

def load_electrochemical_data(filepath):
    """Load electrochemical data from CSV file."""
    data = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def detect_peaks(voltage, current):
    """Simple peak detection algorithm."""
    peaks = []
    threshold = 0.1  # Minimum peak height
    
    for i in range(1, len(current) - 1):
        if current[i] > current[i-1] and current[i] > current[i+1]:
            if current[i] > threshold:
                peaks.append({
                    'voltage': voltage[i],
                    'current': current[i],
                    'index': i
                })
    
    return peaks

def plot_cv_data(voltage, current, peaks, output_path):
    """Plot cyclic voltammetry data with detected peaks."""
    plt.figure(figsize=(10, 6))
    plt.plot(voltage, current, label='CV Curve')
    
    for peak in peaks:
        plt.scatter(peak['voltage'], peak['current'], color='red', zorder=5)
        plt.text(peak['voltage'], peak['current'], 
                f"({peak['voltage']:.2f}, {peak['current']:.2f})",
                fontsize=8, ha='right')
    
    plt.xlabel('Voltage (V)')
    plt.ylabel('Current (A)')
    plt.title('Cyclic Voltammetry Data')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved plot to: {output_path}")

def save_peak_data(peaks, output_path):
    """Save peak data to CSV."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Index', 'Voltage (V)', 'Current (A)'])
        for peak in peaks:
            writer.writerow([peak['index'], peak['voltage'], peak['current']])
    print(f"Saved peak data to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Process electrochemical data')
    parser.add_argument('data_dir', help='Directory containing data files')
    parser.add_argument('--data_file', help='Specific data file to process')
    parser.add_argument('--analysis_type', default='peak_detection',
                        help='Type of analysis to perform')
    parser.add_argument('--output_prefix', default='analysis',
                        help='Prefix for output files')
    
    args = parser.parse_args()
    
    print(f"Starting electrochemical data processing")
    print(f"Data directory: {args.data_dir}")
    print(f"Analysis type: {args.analysis_type}")
    
    # Find data file
    data_file = args.data_file
    if not data_file:
        # Look for common electrochemical data files
        common_patterns = ['*.csv', '*.txt', '*.dat']
        for pattern in common_patterns:
            files = [f for f in os.listdir(args.data_dir) if f.endswith(pattern[1:])]
            if files:
                data_file = files[0]
                break
    
    if not data_file:
        print("ERROR: No data file specified and no common data files found")
        sys.exit(1)
    
    filepath = os.path.join(args.data_dir, data_file)
    if not os.path.exists(filepath):
        print(f"ERROR: Data file not found: {filepath}")
        sys.exit(1)
    
    print(f"Loading data from: {filepath}")
    
    # Load data
    try:
        data = load_electrochemical_data(filepath)
        
        # Assume first two columns are voltage and current
        voltage = [float(row.get('Voltage', row.get('V', 0))) for row in data]
        current = [float(row.get('Current', row.get('I', 0))) for row in data]
        
        if not voltage or not current:
            print("ERROR: Could not extract voltage and current data")
            sys.exit(1)
        
        print(f"Loaded {len(voltage)} data points")
        
        # Perform analysis based on type
        if args.analysis_type == 'peak_detection':
            print("Performing peak detection...")
            peaks = detect_peaks(voltage, current)
            print(f"Found {len(peaks)} peaks")
            
            # Generate timestamp for output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save results
            plot_path = os.path.join(args.data_dir, f"{args.output_prefix}_cv_plot_{timestamp}.png")
            peak_csv_path = os.path.join(args.data_dir, f"{args.output_prefix}_peaks_{timestamp}.csv")
            
            plot_cv_data(voltage, current, peaks, plot_path)
            save_peak_data(peaks, peak_csv_path)
            
            print(f"Analysis complete. Results saved to:")
            print(f"  - Plot: {plot_path}")
            print(f"  - Peak data: {peak_csv_path}")
            
        elif args.analysis_type == 'summary':
            print("Generating summary statistics...")
            voltage_array = np.array(voltage)
            current_array = np.array(current)
            
            summary = {
                'min_voltage': np.min(voltage_array),
                'max_voltage': np.max(voltage_array),
                'min_current': np.min(current_array),
                'max_current': np.max(current_array),
                'mean_current': np.mean(current_array),
                'std_current': np.std(current_array),
                'data_points': len(voltage_array)
            }
            
            print("Summary Statistics:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
            
            # Save summary to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            summary_path = os.path.join(args.data_dir, f"{args.output_prefix}_summary_{timestamp}.txt")
            
            with open(summary_path, 'w') as f:
                for key, value in summary.items():
                    f.write(f"{key}: {value}\n")
            
            print(f"Summary saved to: {summary_path}")
        
        else:
            print(f"ERROR: Unknown analysis type: {args.analysis_type}")
            sys.exit(1)
    
    except Exception as e:
        print(f"ERROR: Processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
