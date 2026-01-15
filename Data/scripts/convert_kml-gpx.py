#!/usr/bin/env python3
"""
Parkrun KML to GPX Converter

This script converts Parkrun KML route files to clean GPX format using 
proper event naming from the Parkruns.xlsx spreadsheet.

Key features:
- Maps KML filenames to event IDs and slugs from Excel data
- Creates clean GPX files with minimal metadata
- Skips existing GPX files to avoid duplicates
- Provides detailed conversion statistics

Author: Route Analysis Project
Date: January 2026
"""

import os
import pandas as pd
from pykml import parser
import gpxpy
import gpxpy.gpx

def load_parkrun_mapping():
    """
    Load parkrun event data from Excel file
    
    Returns:
        pandas.DataFrame: Event data including event_id, event_name, and event_slug
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    excel_path = os.path.join(data_dir, 'Raw_Data', 'Parkruns.xlsx')
    return pd.read_excel(excel_path)

def get_kml_files():
    """
    Scan the Parkrun_KML directory for KML files to convert
    
    Returns:
        list: Full paths to all .kml files in the source directory
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    kml_dir = os.path.join(data_dir, 'GPX', 'Parkun_KML')
    
    kml_files = []
    for file in os.listdir(kml_dir):
        if file.endswith('.kml'):
            kml_files.append(os.path.join(kml_dir, file))
    return sorted(kml_files)  # Sort for consistent processing order

def find_matching_event(kml_filename, parkruns_df):
    """
    Find the corresponding event data for a KML file using robust text matching
    
    Args:
        kml_filename (str): Path to the KML file
        parkruns_df (pandas.DataFrame): Event data from Excel
        
    Returns:
        pandas.Series or None: Event data row if match found, None otherwise
    """
    # Extract base name from KML filename (remove path and extensions)
    base_name = os.path.basename(kml_filename).replace(' parkrun.kml', '').replace('.kml', '')
    
    # Normalize text for better matching (handle apostrophe variants)
    def normalize_text(text):
        """Normalize text by replacing various apostrophe types with standard one"""
        if pd.isna(text):
            return ""
        text = str(text).lower().strip()
        # Replace various apostrophe/quote characters with standard apostrophe
        text = text.replace(''', "'").replace(''', "'").replace('`', "'").replace('´', "'")
        text = text.replace('"', "'").replace('"', "'").replace('″', "'")
        # Handle Unicode replacement character and other encoding issues
        text = text.replace('�', "'").replace('\ufffd', "'")
        return text
    
    normalized_base = normalize_text(base_name)
    
    # Search for matching event using normalized case-insensitive partial matching
    for idx, row in parkruns_df.iterrows():
        if pd.notna(row['event_name']):
            normalized_event = normalize_text(row['event_name'])
            # Check if the base name is contained in the event name
            if normalized_base in normalized_event or normalized_event in normalized_base:
                print(f"  📋 Matched: '{base_name}' → '{row['event_name']}'")
                return row
    
    return None

def kml_to_gpx(kml_file_path, event_name):
    """
    Convert a KML file to ultra-clean GPX format
    
    Args:
        kml_file_path (str): Path to source KML file
        event_name (str): Name of the parkrun event for GPX metadata
        
    Returns:
        gpxpy.gpx.GPX: Ultra-clean GPX object with minimal metadata
    """
    # Parse the KML file
    with open(kml_file_path, 'r', encoding='utf-8') as f:
        root = parser.parse(f).getroot()
    
    # Create a clean GPX object with minimal metadata
    gpx = gpxpy.gpx.GPX()
    gpx.name = f"{event_name} Parkrun Route"
    gpx.description = f"Route data for {event_name} parkrun"
    gpx.creator = "Route Analysis Project"  # Clean creator attribution
    
    # Create a single track for the route
    track = gpxpy.gpx.GPXTrack()
    track.name = f"{event_name} Route"
    gpx.tracks.append(track)
    
    # Create a track segment to hold the route points
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)
    
    # Extract coordinate data from KML structure
    coordinates_found = False
    
    # Iterate through KML elements to find coordinate data
    for elem in root.iter():
        if hasattr(elem, 'tag') and elem.tag.endswith('coordinates'):
            coord_text = elem.text.strip() if elem.text else ""
            if coord_text:
                # Parse KML coordinates format: lon,lat,alt lon,lat,alt ...
                coord_pairs = coord_text.split()
                for coord_pair in coord_pairs:
                    if coord_pair.strip():
                        parts = coord_pair.strip().split(',')
                        if len(parts) >= 2:
                            try:
                                # KML format is longitude, latitude, altitude
                                lon = float(parts[0])
                                lat = float(parts[1])
                                
                                # Only include altitude if it's meaningful (not 0.0)
                                alt = None
                                if len(parts) > 2 and parts[2].strip():
                                    try:
                                        elevation = float(parts[2])
                                        # Only include elevation if it's not zero
                                        if elevation != 0.0:
                                            alt = elevation
                                    except ValueError:
                                        pass
                                
                                # Create clean track point - elevation only if meaningful
                                point = gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon, elevation=alt)
                                segment.points.append(point)
                                coordinates_found = True
                            except (ValueError, IndexError):
                                # Skip invalid coordinate data
                                continue
    
    if not coordinates_found:
        print(f"Warning: No valid coordinates found in {os.path.basename(kml_file_path)}")
    
    return gpx

def convert_parkrun_kmls():
    """
    Main conversion function - processes all KML files in batch
    
    This function:
    1. Loads parkrun event data from Excel
    2. Scans for KML files that need conversion
    3. Matches each KML to its corresponding event data
    4. Converts KML to clean GPX format
    5. Saves GPX files with proper naming convention
    """
    print("Parkrun KML to GPX Converter")
    print("=" * 40)
    
    # Load the parkrun event mapping data
    try:
        parkruns_df = load_parkrun_mapping()
        print(f"Loaded event data for {len(parkruns_df)} parkrun events")
    except Exception as e:
        print(f"Error loading parkrun data: {e}")
        return
    
    # Get list of KML files to process
    kml_files = get_kml_files()
    if not kml_files:
        print("No KML files found to convert")
        return
    
    # Set up output directory structure
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(data_dir, 'GPX', 'Parkrun_GPX')
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Found {len(kml_files)} KML files to process")
    print(f"Output directory: {output_dir}")
    print("\nProcessing files:")
    print("-" * 20)
    
    # Track conversion statistics
    converted_count = 0
    skipped_count = 0
    error_count = 0
    
    # Process each KML file
    for kml_file in kml_files:
        kml_name = os.path.basename(kml_file)
        print(f"\nProcessing: {kml_name}")
        
        # Find corresponding event data
        event_data = find_matching_event(kml_file, parkruns_df)
        
        if event_data is None:
            print(f"  ❌ Error: No matching event found")
            error_count += 1
            continue
        
        # Generate target filename using event ID and slug
        target_filename = f"{event_data['event_id']}_{event_data['event_slug']}.gpx"
        target_path = os.path.join(output_dir, target_filename)
        
        # Skip if GPX file already exists
        if os.path.exists(target_path):
            print(f"  ⏭️  Skipping: {target_filename} already exists")
            skipped_count += 1
            continue
        
        try:
            # Convert KML to clean GPX
            gpx = kml_to_gpx(kml_file, event_data['event_name'])
            
            # Count track points for statistics
            point_count = sum(len(segment.points) for track in gpx.tracks for segment in track.segments)
            
            if point_count == 0:
                print(f"  ⚠️  Warning: No track points extracted")
                error_count += 1
                continue
            
            # Save clean GPX file
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(gpx.to_xml())
            
            print(f"  ✅ Created: {target_filename}")
            print(f"     Track points: {point_count}")
            converted_count += 1
            
        except Exception as e:
            print(f"  ❌ Error converting {kml_name}: {str(e)}")
            error_count += 1
    
    # Print final statistics
    print("\n" + "=" * 40)
    print("Conversion Summary:")
    print(f"  Successfully converted: {converted_count}")
    print(f"  Skipped (already exist): {skipped_count}")
    print(f"  Errors encountered: {error_count}")
    print(f"  Total files processed: {len(kml_files)}")
    
    if converted_count > 0:
        print(f"\n✅ {converted_count} new GPX files created in Parkrun_GPX folder")
    
    if error_count > 0:
        print(f"\n⚠️  {error_count} files had issues - check output above for details")

if __name__ == "__main__":
    convert_parkrun_kmls()
