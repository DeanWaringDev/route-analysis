#!/usr/bin/env python3
"""
Populate Events_2026.xlsx with data from enhanced GPX files

This script extracts data from enhanced 2026 event GPX files and updates the
Events_2026.xlsx spreadsheet with:
- region (from postcode)
- start_lat, start_lon, finish_lat, finish_lon (from GPX)
- route_source = "Enhanced" (if currently "Event")
- gpx_available = True  
- gpx_point_count (points with elevation)
- gpx_resolution_class (low/medium/high based on point count)

Does NOT overwrite existing data except for route_source, gpx_point_count, and gpx_resolution_class
"""

import os
import pandas as pd
import gpxpy
import re
import argparse

def extract_region_from_postcode(postcode):
    """
    Extract region from UK postcode
    
    Args:
        postcode (str): UK postcode like "NN16 8YH"
        
    Returns:
        str: Region name
    """
    if not postcode or pd.isna(postcode):
        return "Unknown"
    
    # Extract the area code (first 1-2 letters)
    area_match = re.match(r'([A-Z]{1,2})', str(postcode).strip().upper())
    if not area_match:
        return "Unknown"
    
    area_code = area_match.group(1)
    
    # Map area codes to regions
    region_map = {
        'NN': 'Northamptonshire',
        'PE': 'Lincolnshire', 
        'LN': 'Lincolnshire',
        'LE': 'Leicestershire',
        'MK': 'Buckinghamshire',
        'LU': 'Bedfordshire',
        'SG': 'Hertfordshire',
        'CB': 'Cambridgeshire',
        'NR': 'Norfolk',
        'IP': 'Suffolk',
        'CO': 'Essex',
        'CV': 'Warwickshire',
        'B': 'West Midlands',
        'DE': 'Derbyshire',
        'NG': 'Nottinghamshire',
        'S': 'South Yorkshire',
        'DN': 'North Lincolnshire',
        'HU': 'East Yorkshire',
        'WS': 'Staffordshire'
    }
    
    return region_map.get(area_code, f"Area_{area_code}")

def extract_gpx_data(gpx_file_path):
    """
    Extract relevant data from GPX file
    
    Args:
        gpx_file_path (str): Path to GPX file
        
    Returns:
        dict: Dictionary with extracted data
    """
    try:
        with open(gpx_file_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
        
        # Extract all points from both tracks and routes
        all_points = []
        
        # Get points from tracks
        for track in gpx.tracks:
            for segment in track.segments:
                all_points.extend(segment.points)
        
        # Get points from routes (if no tracks found)
        if not all_points:
            for route in gpx.routes:
                all_points.extend(route.points)
        
        if not all_points:
            return None
            
        # Get start and finish coordinates
        start_point = all_points[0]
        finish_point = all_points[-1]
        
        # Count points with elevation
        points_with_elevation = sum(1 for point in all_points if point.elevation is not None)
        
        # Determine resolution class (same logic as parkruns)
        if points_with_elevation < 400:
            resolution_class = "low"
        elif points_with_elevation <= 599:
            resolution_class = "medium"
        else:
            resolution_class = "high"
        
        return {
            'start_lat': start_point.latitude,
            'start_lon': start_point.longitude,
            'finish_lat': finish_point.latitude,
            'finish_lon': finish_point.longitude,
            'gpx_point_count': points_with_elevation,
            'gpx_resolution_class': resolution_class
        }
        
    except Exception as e:
        print(f"Error processing {gpx_file_path}: {e}")
        return None

def populate_events_2026_data(force_update=False):
    """
    Main function to populate the Events_2026.xlsx file
    
    Args:
        force_update (bool): If True, overwrite existing data. If False, only fill missing data.
    """
    # File paths
    excel_path = os.path.join('..', 'Raw_Data', 'Events_2026.xlsx')
    enhanced_gpx_dir = os.path.join('..', 'GPX', 'Events_2026_ENH')
    
    print(f"🔄 Loading Events_2026.xlsx... (force_update={force_update})")
    try:
        df = pd.read_excel(excel_path)
        print(f"📊 Found {len(df)} event records")
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return
    
    print(f"📁 Scanning {enhanced_gpx_dir} for enhanced GPX files...")
    
    updates_made = 0
    
    for index, row in df.iterrows():
        event_id = row['event_id']
        event_name = row['event_name']
        postcode = row['event_postcode'] if 'event_postcode' in row else None
        
        # Skip rows with missing data
        if pd.isna(event_id) or pd.isna(event_name):
            print(f"⚠️  Skipping row {index} - missing event_id or event_name")
            continue
            
        print(f"\n🏃 Processing {event_id} - {event_name}")
        
        # Update region from postcode (only if missing or force)
        if postcode and (force_update or pd.isna(row.get('region')) or not row.get('region')):
            region = extract_region_from_postcode(postcode)
            df.at[index, 'region'] = region
            print(f"  📍 Region: {postcode} → {region}")
        
        # Look for corresponding enhanced GPX file by event_id
        potential_filenames = [
            f"{event_id}_ENH.gpx",  # Standard pattern
            f"{event_id}_enhanced.gpx"  # Alternative pattern
        ]
        
        gpx_path = None
        gpx_filename = None
        
        for filename in potential_filenames:
            test_path = os.path.join(enhanced_gpx_dir, filename)
            if os.path.exists(test_path):
                # Check if it matches our event_id pattern (starts with the event_id)
                if filename.startswith(str(event_id)):
                    gpx_path = test_path
                    gpx_filename = filename
                    break
        
        # Also check for files that start with event_id and contain event name
        if not gpx_path:
            for filename in os.listdir(enhanced_gpx_dir):
                if (filename.lower().endswith('_enh.gpx') and 
                    filename.startswith(str(event_id))):
                    gpx_path = os.path.join(enhanced_gpx_dir, filename)
                    gpx_filename = filename
                    break
        
        if gpx_path:
            print(f"  📄 Found enhanced GPX: {gpx_filename}")
            
            # Check if we should update coordinates (force or missing data)
            should_update_coords = force_update or pd.isna(row.get('start_lat'))
            
            # Always update route_source, gpx_point_count, gpx_resolution_class
            should_update_gpx_meta = True
            
            if should_update_coords or should_update_gpx_meta:
                # Extract GPX data
                gpx_data = extract_gpx_data(gpx_path)
                
                if gpx_data:
                    # Update coordinates (only if force or missing)
                    if should_update_coords:
                        df.at[index, 'start_lat'] = float(gpx_data['start_lat'])
                        df.at[index, 'start_lon'] = float(gpx_data['start_lon'])
                        df.at[index, 'finish_lat'] = float(gpx_data['finish_lat'])
                        df.at[index, 'finish_lon'] = float(gpx_data['finish_lon'])
                        print(f"      📍 Coordinates updated")
                        print(f"      Start: {gpx_data['start_lat']:.6f}, {gpx_data['start_lon']:.6f}")
                        print(f"      Finish: {gpx_data['finish_lat']:.6f}, {gpx_data['finish_lon']:.6f}")
                    
                    # Always update GPX metadata
                    df.at[index, 'gpx_available'] = 1  # Use 1 instead of True for Excel compatibility
                    df.at[index, 'gpx_point_count'] = int(gpx_data['gpx_point_count'])
                    df.at[index, 'gpx_resolution_class'] = gpx_data['gpx_resolution_class']
                    
                    # Update route_source if currently "Event"
                    current_route_source = row.get('route_source', '')
                    if current_route_source == 'Event' or pd.isna(current_route_source):
                        df.at[index, 'route_source'] = "Enhanced"
                        print(f"      📂 Route source: {current_route_source} → Enhanced")
                    
                    print(f"  ✅ Updated: {gpx_data['gpx_point_count']} points ({gpx_data['gpx_resolution_class']} resolution)")
                    
                    updates_made += 1
                else:
                    print(f"  ❌ Failed to extract data from GPX")
            else:
                print(f"  ⏭️  Data already exists (use --force to overwrite coordinates)")
        else:
            print(f"  ⚠️  No enhanced GPX found. Tried:")
            for filename in potential_filenames:
                print(f"      - {filename}")
            # Also check what files are actually there
            if os.path.exists(enhanced_gpx_dir):
                actual_files = [f for f in os.listdir(enhanced_gpx_dir) if f.startswith(str(event_id))]
                if actual_files:
                    print(f"      Available files starting with {event_id}: {actual_files}")
    
    # Save updated Excel file
    if updates_made > 0:
        print(f"\n💾 Saving updated Excel file...")
        try:
            df.to_excel(excel_path, index=False)
            print(f"✅ Successfully updated {updates_made} event records")
            print(f"📄 File saved: {excel_path}")
        except PermissionError:
            print(f"❌ Permission denied: Cannot save to {excel_path}")
            print(f"💡 Please close Excel and run the script again")
        except Exception as e:
            print(f"❌ Error saving Excel file: {e}")
    else:
        print(f"\n⚠️  No updates made to Excel file")
    
    print(f"\n📊 Summary:")
    print(f"  Total events: {len(df)}")
    print(f"  Updated records: {updates_made}")
    print(f"  Enhanced GPX files processed: {updates_made}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Populate Events_2026.xlsx with enhanced GPX data')
    parser.add_argument('--force', action='store_true', 
                       help='Force update existing coordinate data (default: only fill missing coordinates, always update GPX metadata)')
    
    args = parser.parse_args()
    populate_events_2026_data(force_update=args.force)