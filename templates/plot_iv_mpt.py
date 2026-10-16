#!/usr/bin/env python3
"""
Processing script for BioLogic EC-Lab .mpt files.

This script reads a .mpt file, extracts Ewe/V and <I>/mA data,
plots Ewe as a function of <I>, and saves the plot.

Usage:
    This script is sent via email with [RUN] in the subject line.
    
    Email format:
    - Subject: [RUN] Plot IV curve from MPT file
    - Body:
        Recipients: jaroslav@herman.cz
        data_file: IV_Day1_Procedure1_03_SV_C01.mpt
        output_prefix: iv_plot
    - Attachment: this script file

The processor will save this script and execute it with the data directory.
"""

import argparse
import os
import sys
import matplotlib.pyplot as plt


def read_mpt_file(filepath):
    """Read BioLogic EC-Lab .mpt file and extract data columns."""
    try:
        import eclabfiles as ecf
        
        # Parse the .mpt file
        data, meta = ecf.process(filepath)
        
        # Convert to pandas DataFrame
        df = ecf.to_df(filepath)
        
        return df, meta
        
    except ImportError:
        # Fallback: try to parse as tab-delimited text file with header
        print("eclabfiles not available, trying manual parsing...")
        return read_mpt_file_manual(filepath)
    except Exception as e:
        print(f"Error reading with eclabfiles: {e}")
        return read_mpt_file_manual(filepath)


def read_mpt_file_manual(filepath):
    """Manually read .mpt file as tab-delimited text with header lines."""
    import pandas as pd
    
    # Read the file, skipping header lines
    # The user mentioned first two rows contain:
    # "EC-Lab ASCII FILE" and "Nb header lines : 64"
    # So we need to skip 64 lines
    
    try:
        # First, read the header to find the number of header lines
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            second_line = f.readline().strip()
            
        # Parse the number of header lines from second line
        # Expected format: "Nb header lines : 64"
        num_header_lines = 64
        if 'Nb header lines' in second_line:
            try:
                num_header_lines = int(second_line.split(':')[1].strip())
            except (ValueError, IndexError):
                num_header_lines = 64
        
        # Read the data, skipping header lines
        df = pd.read_csv(
            filepath,
            sep='\t',
            skiprows=num_header_lines,
            encoding='utf-8',
            on_bad_lines='warn'
        )
        
        return df, {'source': 'manual_parse', 'header_lines': num_header_lines}
        
    except Exception as e:
        print(f"Error reading file manually: {e}")
        raise


def plot_iv_curve(df, output_path, title=None):
    """Plot Ewe/V as a function of <I>/mA."""
    
    # Check for required columns
    # Common column names in EC-Lab .mpt files:
    # Ewe/V, <Ewe>/V, Ewe (V), Potential/V
    # <I>/mA, I/mA, <I> (mA), Current/mA
    
    ewe_columns = ['<Ewe>/V', 'Ewe/V', 'Ewe (V)', 'Potential/V', '<Ewe> (V)']
    current_columns = ['<I>/mA', 'I/mA', '<I> (mA)', 'Current/mA', 'I (mA)']
    
    # Find the Ewe column
    ewe_col = None
    for col in ewe_columns:
        # Check exact match
        if col in df.columns:
            ewe_col = col
            break
        # Check case-insensitive match
        for existing_col in df.columns:
            if existing_col.strip().lower() == col.lower():
                ewe_col = existing_col
                break
        if ewe_col:
            break
    
    # Find the current column
    current_col = None
    for col in current_columns:
        if col in df.columns:
            current_col = col
            break
        for existing_col in df.columns:
            if existing_col.strip().lower() == col.lower():
                current_col = existing_col
                break
        if current_col:
            break
    
    if ewe_col is None:
        print(f"ERROR: Could not find Ewe column. Available columns: {list(df.columns)}")
        # Try to find any column with 'Ewe' or 'V' in it
        for col in df.columns:
            if 'Ewe' in col or 'V' in col.upper():
                ewe_col = col
                print(f"  Trying column: {ewe_col}")
                break
        if ewe_col is None:
            raise ValueError("No Ewe/V column found in data")
    
    if current_col is None:
        print(f"ERROR: Could not find current column. Available columns: {list(df.columns)}")
        # Try to find any column with 'I' or 'mA' in it
        for col in df.columns:
            if 'I' in col or 'mA' in col:
                current_col = col
                print(f"  Trying column: {current_col}")
                break
        if current_col is None:
            raise ValueError("No <I>/mA column found in data")
    
    print(f"Using Ewe column: {ewe_col}")
    print(f"Using current column: {current_col}")
    
    # Extract data
    try:
        ewe = df[ewe_col].values
        current = df[current_col].values
    except KeyError as e:
        print(f"ERROR: Could not access column: {e}")
        raise
    
    # Create the plot
    plt.figure(figsize=(10, 6))
    plt.plot(current, ewe, 'b-', linewidth=2, marker='o', markersize=4)
    
    plt.xlabel(f'{current_col}')
    plt.ylabel(f'{ewe_col}')
    plt.title(title or f'Ewe vs <I> curve')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Save the plot
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Plot saved to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Plot Ewe/V vs <I>/mA from BioLogic .mpt file'
    )
    parser.add_argument('data_dir', help='Directory containing data files')
    parser.add_argument('--data_file', 
                        default='IV_Day1_Procedure1_03_SV_C01.mpt',
                        help='Specific .mpt file to process')
    parser.add_argument('--output_prefix', 
                        default='iv_curve',
                        help='Prefix for output files')
    parser.add_argument('--title', 
                        default=None,
                        help='Title for the plot')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("BioLogic .mpt IV Curve Plotter")
    print("=" * 60)
    print(f"Data directory: {args.data_dir}")
    print(f"Data file: {args.data_file}")
    print(f"Output prefix: {args.output_prefix}")
    
    # Construct full file path
    filepath = os.path.join(args.data_dir, args.data_file)
    
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        # Try to find .mpt files in the directory
        mpt_files = [f for f in os.listdir(args.data_dir) if f.endswith('.mpt')]
        if mpt_files:
            print(f"Available .mpt files: {mpt_files}")
            filepath = os.path.join(args.data_dir, mpt_files[0])
            print(f"Using first available file: {filepath}")
        else:
            print("No .mpt files found in directory")
            sys.exit(1)
    
    print(f"Reading file: {filepath}")
    
    try:
        # Read the .mpt file
        df, meta = read_mpt_file(filepath)
        
        print(f"Loaded {len(df)} data points")
        print(f"Columns: {list(df.columns)}")
        print(f"Metadata: {meta}")
        
        # Generate timestamp for output files
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output filename
        plot_filename = f"{args.output_prefix}_{timestamp}.png"
        plot_path = os.path.join(args.data_dir, plot_filename)
        
        # Create plot
        plot_title = args.title or f"IV Curve: {args.data_file}"
        plot_iv_curve(df, plot_path, title=plot_title)
        
        # Also save the data as CSV for reference
        csv_filename = f"{args.output_prefix}_{timestamp}.csv"
        csv_path = os.path.join(args.data_dir, csv_filename)
        df.to_csv(csv_path, index=False)
        print(f"Data saved to: {csv_path}")
        
        print("\nProcessing complete!")
        print(f"  Plot: {plot_path}")
        print(f"  CSV: {csv_path}")
        
    except Exception as e:
        print(f"ERROR: Processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
