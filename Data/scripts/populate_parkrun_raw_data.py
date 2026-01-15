#!/usr/bin/env python3
"""
Populate Parkruns.xlsx with data from enhanced GPX files

This script extracts data from enhanced parkrun GPX files and updates the
Parkruns.xlsx spreadsheet with:
- region (from postcode)
- start_lat, start_lon, finish_lat, finish_lon (from GPX)
- power_of_10 = True
- gpx_available = True  
- route_source = "Enhanced"
- gpx_point_count (points with elevation)
- gpx_resolution_class (low/medium/high based on point count)
- analysis_ready = False
"""

import os
import pandas as pd
import gpxpy
import re
import argparse

def slugify_event_name(text):
    """
    Convert event name to safe filename component
    
    Args:
        text (str): Event name like "King's Lynn" or "Market Harborough"
        
    Returns:
        str: Slugified name like "kingslynn" or "marketharborough"
    """
    if not text or pd.isna(text):
        return "unknown"
    
    # Convert to lowercase and handle special cases
    slug = str(text).lower()
    
    # Replace common variations
    slug = slug.replace("st.", "st")
    slug = slug.replace("&", "and")
    
    # Keep only alphanumeric characters, replace everything else with underscore
    slug = re.sub(r'[^a-z0-9]', '_', slug)
    
    # Collapse multiple underscores
    slug = re.sub(r'_+', '_', slug)
    
    # Remove leading/trailing underscores
    slug = slug.strip('_')
    
    return slug

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
        'HU': 'East Yorkshire'
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
        
        # Determine resolution class
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

def populate_parkrun_data(force_update=False):
    """
    Main function to populate the Parkruns.xlsx file
    
    Args:
        force_update (bool): If True, overwrite existing data. If False, only fill missing data.
    """
    # File paths
    excel_path = os.path.join('..', 'Raw_Data', 'Parkruns.xlsx')
    enhanced_gpx_dir = os.path.join('..', 'GPX', 'Parkrun_ENH')
    
    print(f"🔄 Loading Parkruns.xlsx... (force_update={force_update})")
    try:
        df = pd.read_excel(excel_path)
        print(f"📊 Found {len(df)} parkrun records")
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return
    
    print(f"📁 Scanning {enhanced_gpx_dir} for enhanced GPX files...")
    
    updates_made = 0
    
    for index, row in df.iterrows():
        event_id = row['event_id']
        event_name = row['event_name']
        postcode = row['event_postcode']
        
        # Skip rows with missing data
        if pd.isna(event_id) or pd.isna(event_name):
            print(f"⚠️  Skipping row {index} - missing event_id or event_name")
            continue
            
        print(f"\n🏃 Processing {event_id} - {event_name}")
        
        # Update region from postcode (only if missing or force)
        if force_update or pd.isna(row['region']) or not row['region']:
            region = extract_region_from_postcode(postcode)
            df.at[index, 'region'] = region
            print(f"  📍 Region: {postcode} → {region}")
        
        # Look for corresponding enhanced GPX file using robust slugify
        name_slug = slugify_event_name(event_name)
        
        # Try multiple filename patterns
        potential_filenames = [
            f"{event_id}_{name_slug}_ENH.gpx",  # Full name
            f"{event_id}_ENH.gpx",              # ID only
            f'{event_id}_{event_name.lower().replace(" ", "").replace("\'", "")}_ENH.gpx'  # Fallback to old method
        ]
        
        gpx_path = None
        gpx_filename = None
        
        for filename in potential_filenames:
            test_path = os.path.join(enhanced_gpx_dir, filename)
            if os.path.exists(test_path):
                gpx_path = test_path
                gpx_filename = filename
                break
        
        if gpx_path:
            print(f"  📄 Found enhanced GPX: {gpx_filename}")
            
            # Check if we should update (force or missing data)
            should_update = force_update or pd.isna(row['start_lat']) or pd.isna(row['route_source']) or row['route_source'] != 'Enhanced'
            
            if should_update:
                # Extract GPX data
                gpx_data = extract_gpx_data(gpx_path)
                
                if gpx_data:
                    # Update coordinates
                    df.at[index, 'start_lat'] = float(gpx_data['start_lat'])
                    df.at[index, 'start_lon'] = float(gpx_data['start_lon'])
                    df.at[index, 'finish_lat'] = float(gpx_data['finish_lat'])
                    df.at[index, 'finish_lon'] = float(gpx_data['finish_lon'])
                    
                    # Update GPX metadata
                    df.at[index, 'power_of_10'] = 1  # Use 1 instead of True for Excel compatibility
                    df.at[index, 'gpx_available'] = 1  # Use 1 instead of True for Excel compatibility
                    df.at[index, 'route_source'] = "Enhanced"
                    df.at[index, 'gpx_point_count'] = int(gpx_data['gpx_point_count'])
                    df.at[index, 'gpx_resolution_class'] = gpx_data['gpx_resolution_class']
                    # Don't automatically reset analysis_ready - preserve existing progress
                    
                    print(f"  ✅ Updated: {gpx_data['gpx_point_count']} points ({gpx_data['gpx_resolution_class']} resolution)")
                    print(f"      Start: {gpx_data['start_lat']:.6f}, {gpx_data['start_lon']:.6f}")
                    print(f"      Finish: {gpx_data['finish_lat']:.6f}, {gpx_data['finish_lon']:.6f}")
                    
                    updates_made += 1
                else:
                    print(f"  ❌ Failed to extract data from GPX")
            else:
                print(f"  ⏭️  Data already exists (use --force to overwrite)")
        else:
            print(f"  ⚠️  No enhanced GPX found. Tried:")
            for filename in potential_filenames:
                print(f"      - {filename}")
    
    # Save updated Excel file
    if updates_made > 0:
        print(f"\n💾 Saving updated Excel file...")
        try:
            df.to_excel(excel_path, index=False)
            print(f"✅ Successfully updated {updates_made} parkrun records")
            print(f"📄 File saved: {excel_path}")
        except PermissionError:
            print(f"❌ Permission denied: Cannot save to {excel_path}")
            print(f"💡 Please close Excel and run the script again")
        except Exception as e:
            print(f"❌ Error saving Excel file: {e}")
    else:
        print(f"\n⚠️  No updates made to Excel file")
    
    print(f"\n📊 Summary:")
    print(f"  Total parkruns: {len(df)}")
    print(f"  Updated records: {updates_made}")
    print(f"  Enhanced GPX files processed: {updates_made}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Populate Parkruns.xlsx with enhanced GPX data')
    parser.add_argument('--force', action='store_true', 
                       help='Force update existing data (default: only fill missing data)')
    
    args = parser.parse_args()
    populate_parkrun_data(force_update=args.force)
