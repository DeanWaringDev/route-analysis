#!/usr/bin/env python3
"""
Enhanced Elevation Analysis and Validation System

This script will:
1. Validate accuracy of existing elevation data in enhanced GPX files
2. Get additional elevation data from APIs for cross-validation
3. Create detailed elevation tables for parkruns, 2026 events, and 2027 events
4. Calculate gradients, elevation profiles, and accessibility metrics
"""

import os
import pandas as pd
import gpxpy
import requests
import time
import json
import numpy as np
from math import radians, cos, sin, asin, sqrt
from datetime import datetime

class ElevationAnalyzer:
    def __init__(self):
        self.api_delay = 0.1  # Delay between API calls to be respectful
        self.max_batch_size = 512  # Maximum points per API request
        
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two GPS points in meters"""
        R = 6371000  # Earth radius in meters
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 2 * R * asin(sqrt(a))
    
    def get_elevation_from_api(self, points):
        """
        Get elevation data from Open-Elevation API
        
        Args:
            points: List of (lat, lon) tuples
            
        Returns:
            List of elevation values or None on error
        """
        if not points:
            return None
            
        try:
            # Prepare the request data
            locations = [{"latitude": lat, "longitude": lon} for lat, lon in points]
            
            # Split into batches if needed
            all_elevations = []
            
            for i in range(0, len(locations), self.max_batch_size):
                batch = locations[i:i + self.max_batch_size]
                
                response = requests.post(
                    "https://api.open-elevation.com/api/v1/lookup",
                    json={"locations": batch},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    batch_elevations = [result["elevation"] for result in data["results"]]
                    all_elevations.extend(batch_elevations)
                else:
                    print(f"    ⚠️  API request failed: {response.status_code}")
                    return None
                
                # Be respectful to the API
                if i + self.max_batch_size < len(locations):
                    time.sleep(self.api_delay)
            
            return all_elevations
            
        except Exception as e:
            print(f"    ❌ API Error: {e}")
            return None
    
    def load_gpx_elevation_data(self, gpx_file_path):
        """
        Load elevation data from GPX file
        
        Returns:
            dict with elevation analysis data
        """
        try:
            with open(gpx_file_path, 'r', encoding='utf-8') as gpx_file:
                gpx = gpxpy.parse(gpx_file)
            
            # Extract all points
            all_points = []
            for track in gpx.tracks:
                for segment in track.segments:
                    all_points.extend(segment.points)
            
            if not all_points:
                return None
            
            # Extract coordinates and elevations
            coordinates = [(p.latitude, p.longitude) for p in all_points]
            elevations = [p.elevation for p in all_points if p.elevation is not None]
            
            # Calculate distances along route
            distances = [0]
            for i in range(1, len(coordinates)):
                dist = self.haversine_distance(
                    coordinates[i-1][0], coordinates[i-1][1],
                    coordinates[i][0], coordinates[i][1]
                )
                distances.append(distances[-1] + dist)
            
            # Calculate basic statistics
            if elevations:
                elevation_stats = {
                    'min_elevation': min(elevations),
                    'max_elevation': max(elevations),
                    'elevation_gain': sum(max(0, elevations[i] - elevations[i-1]) for i in range(1, len(elevations))),
                    'elevation_loss': sum(max(0, elevations[i-1] - elevations[i]) for i in range(1, len(elevations))),
                    'avg_elevation': sum(elevations) / len(elevations)
                }
            else:
                elevation_stats = {
                    'min_elevation': None,
                    'max_elevation': None, 
                    'elevation_gain': None,
                    'elevation_loss': None,
                    'avg_elevation': None
                }
            
            return {
                'coordinates': coordinates,
                'elevations': elevations,
                'distances': distances,
                'total_distance': distances[-1] if distances else 0,
                'point_count': len(all_points),
                'elevation_coverage': len(elevations) / len(all_points) * 100 if all_points else 0,
                **elevation_stats
            }
            
        except Exception as e:
            print(f"Error processing {gpx_file_path}: {e}")
            return None
    
    def calculate_gradients(self, coordinates, elevations, distances):
        """Calculate gradients along the route"""
        if len(elevations) < 2:
            return []
        
        gradients = []
        for i in range(1, len(elevations)):
            dist_diff = distances[i] - distances[i-1]
            elev_diff = elevations[i] - elevations[i-1]
            
            if dist_diff > 0:
                gradient_percent = (elev_diff / dist_diff) * 100
                gradients.append(gradient_percent)
            else:
                gradients.append(0)
        
        return gradients
    
    def analyze_accessibility(self, gradients, distances):
        """Analyze wheelchair accessibility based on gradients with derived presentation layer"""
        if not gradients:
            return {
                'max_gradient': None,
                'avg_gradient': None,
                'steep_sections_5pct': 0,
                'steep_sections_8pct': 0,
                'accessibility_rating': 'Unknown',
                # Derived presentation layer
                'steep_5pct_distance_m': 0,
                'steep_5pct_route_percentage': 0,
                'steep_5pct_continuous_stretches': 0,
                'steep_5pct_avg_stretch_length_m': 0,
                'steep_5pct_longest_stretch_m': 0,
                'steep_8pct_distance_m': 0,
                'steep_8pct_route_percentage': 0,
                'steep_8pct_continuous_stretches': 0,
                'steep_8pct_avg_stretch_length_m': 0,
                'steep_8pct_longest_stretch_m': 0
            }
        
        # Raw point analysis (internal)
        steep_5pct_points = [i for i, g in enumerate(gradients) if abs(g) > 5]
        steep_8pct_points = [i for i, g in enumerate(gradients) if abs(g) > 8]
        max_gradient = max(abs(g) for g in gradients)
        avg_gradient = sum(abs(g) for g in gradients) / len(gradients)
        
        # Derived presentation layer analysis
        def group_continuous_stretches(steep_points, distances):
            """Group consecutive steep points into continuous stretches"""
            if not steep_points:
                return [], 0, 0, 0, 0
            
            stretches = []
            current_stretch_start = steep_points[0]
            current_stretch_end = steep_points[0]
            
            for i in range(1, len(steep_points)):
                if steep_points[i] == steep_points[i-1] + 1:
                    # Consecutive point, extend current stretch
                    current_stretch_end = steep_points[i]
                else:
                    # Gap found, finalize current stretch and start new one
                    stretch_start_dist = distances[current_stretch_start]
                    stretch_end_dist = distances[current_stretch_end + 1] if current_stretch_end + 1 < len(distances) else distances[current_stretch_end]
                    stretch_length = stretch_end_dist - stretch_start_dist
                    stretches.append({
                        'start_distance': stretch_start_dist,
                        'end_distance': stretch_end_dist,
                        'length': stretch_length
                    })
                    current_stretch_start = steep_points[i]
                    current_stretch_end = steep_points[i]
            
            # Add final stretch
            stretch_start_dist = distances[current_stretch_start]
            stretch_end_dist = distances[current_stretch_end + 1] if current_stretch_end + 1 < len(distances) else distances[current_stretch_end]
            stretch_length = stretch_end_dist - stretch_start_dist
            stretches.append({
                'start_distance': stretch_start_dist,
                'end_distance': stretch_end_dist,
                'length': stretch_length
            })
            
            # Calculate derived metrics
            total_steep_distance = sum(s['length'] for s in stretches)
            total_route_distance = distances[-1] if distances else 1
            route_percentage = (total_steep_distance / total_route_distance) * 100
            num_stretches = len(stretches)
            avg_stretch_length = total_steep_distance / num_stretches if num_stretches > 0 else 0
            longest_stretch = max(s['length'] for s in stretches) if stretches else 0
            
            return stretches, total_steep_distance, route_percentage, avg_stretch_length, longest_stretch
        
        # Analyze 5% gradient stretches
        stretches_5pct, distance_5pct, route_pct_5pct, avg_stretch_5pct, longest_stretch_5pct = group_continuous_stretches(steep_5pct_points, distances)
        
        # Analyze 8% gradient stretches  
        stretches_8pct, distance_8pct, route_pct_8pct, avg_stretch_8pct, longest_stretch_8pct = group_continuous_stretches(steep_8pct_points, distances)
        
        # Accessibility rating
        if max_gradient <= 5:
            rating = 'Excellent'
        elif max_gradient <= 8 and route_pct_5pct < 10:
            rating = 'Good'
        elif max_gradient <= 12 and route_pct_8pct < 5:
            rating = 'Moderate'
        else:
            rating = 'Challenging'
        
        return {
            # Raw internal metrics (for compatibility)
            'max_gradient': max_gradient,
            'avg_gradient': avg_gradient,
            'steep_sections_5pct': len(steep_5pct_points),
            'steep_sections_8pct': len(steep_8pct_points),
            'steep_5pct_percentage': len(steep_5pct_points) / len(gradients) * 100,
            'steep_8pct_percentage': len(steep_8pct_points) / len(gradients) * 100,
            'accessibility_rating': rating,
            
            # Derived presentation layer (human-readable)
            'steep_5pct_distance_m': round(distance_5pct, 1),
            'steep_5pct_route_percentage': round(route_pct_5pct, 1),
            'steep_5pct_continuous_stretches': len(stretches_5pct),
            'steep_5pct_avg_stretch_length_m': round(avg_stretch_5pct, 1),
            'steep_5pct_longest_stretch_m': round(longest_stretch_5pct, 1),
            'steep_8pct_distance_m': round(distance_8pct, 1),
            'steep_8pct_route_percentage': round(route_pct_8pct, 1),
            'steep_8pct_continuous_stretches': len(stretches_8pct),
            'steep_8pct_avg_stretch_length_m': round(avg_stretch_8pct, 1),
            'steep_8pct_longest_stretch_m': round(longest_stretch_8pct, 1)
        }
    
    def validate_with_api(self, gpx_data, sample_points=50):
        """Validate elevation data with API"""
        if not gpx_data or not gpx_data['coordinates']:
            return None
        
        # Sample points for validation (to avoid overwhelming API)
        coords = gpx_data['coordinates']
        if len(coords) > sample_points:
            step = len(coords) // sample_points
            sample_coords = coords[::step]
        else:
            sample_coords = coords
        
        print(f"    🌐 Validating {len(sample_coords)} points with elevation API...")
        
        # Get API elevations
        api_elevations = self.get_elevation_from_api(sample_coords)
        
        if not api_elevations:
            return None
        
        # Compare with existing elevations
        gpx_elevations = gpx_data['elevations']
        if len(coords) > sample_points and gpx_elevations:
            step = len(coords) // sample_points
            sample_gpx_elevations = gpx_elevations[::step]
        else:
            sample_gpx_elevations = gpx_elevations
        
        if len(sample_gpx_elevations) != len(api_elevations):
            return None
        
        # Calculate differences
        differences = [abs(api - gpx) for api, gpx in zip(api_elevations, sample_gpx_elevations)]
        
        return {
            'api_elevations': api_elevations,
            'gpx_elevations': sample_gpx_elevations,
            'differences': differences,
            'avg_difference': sum(differences) / len(differences),
            'max_difference': max(differences),
            'validation_points': len(sample_coords)
        }
    
    def process_enhanced_gpx_files(self):
        """Process all enhanced GPX files and create elevation tables"""
        
        folders = {
            'parkrun': os.path.join('..', 'GPX', 'Parkrun_ENH'),
            'events_2026': os.path.join('..', 'GPX', 'Events_2026_ENH'),
            'events_2027': os.path.join('..', 'GPX', 'Events_2027_ENH')
        }
        
        all_results = {}
        
        for category, folder_path in folders.items():
            if not os.path.exists(folder_path):
                print(f"⚠️  Folder not found: {folder_path}")
                continue
            
            print(f"\n🏔️  Processing {category.upper()} elevation data...")
            print(f"📁 Folder: {folder_path}")
            
            gpx_files = [f for f in os.listdir(folder_path) if f.lower().endswith('_enh.gpx')]
            
            if not gpx_files:
                print(f"  No enhanced GPX files found")
                continue
            
            category_results = []
            
            for filename in sorted(gpx_files):
                file_path = os.path.join(folder_path, filename)
                print(f"\n  📄 Analyzing: {filename}")
                
                # Load GPX data
                gpx_data = self.load_gpx_elevation_data(file_path)
                if not gpx_data:
                    print(f"    ❌ Failed to load GPX data")
                    continue
                
                # Calculate gradients
                gradients = self.calculate_gradients(
                    gpx_data['coordinates'], 
                    gpx_data['elevations'], 
                    gpx_data['distances']
                )
                
                # Analyze accessibility
                accessibility = self.analyze_accessibility(gradients, gpx_data['distances'])
                
                # Validate with API (sample points to avoid overwhelming API)
                validation = self.validate_with_api(gpx_data, sample_points=25)
                
                # Compile results
                result = {
                    'event_id': filename.split('_')[0] if '_' in filename else filename.replace('_ENH.gpx', '').replace('.gpx', ''),
                    'filename': filename,
                    'total_distance_m': gpx_data['total_distance'],
                    'total_distance_km': gpx_data['total_distance'] / 1000,
                    'point_count': gpx_data['point_count'],
                    'elevation_coverage_pct': gpx_data['elevation_coverage'],
                    'min_elevation_m': gpx_data['min_elevation'],
                    'max_elevation_m': gpx_data['max_elevation'],
                    'elevation_range_m': gpx_data['max_elevation'] - gpx_data['min_elevation'] if gpx_data['max_elevation'] and gpx_data['min_elevation'] else None,
                    'total_elevation_gain_m': gpx_data['elevation_gain'],
                    'total_elevation_loss_m': gpx_data['elevation_loss'],
                    'avg_elevation_m': gpx_data['avg_elevation'],
                    'max_gradient_pct': accessibility['max_gradient'],
                    'avg_gradient_pct': accessibility['avg_gradient'],
                    'steep_sections_5pct_count': accessibility['steep_sections_5pct'],
                    'steep_sections_8pct_count': accessibility['steep_sections_8pct'],
                    'steep_5pct_percentage': accessibility['steep_5pct_percentage'],
                    'steep_8pct_percentage': accessibility['steep_8pct_percentage'],
                    'accessibility_rating': accessibility['accessibility_rating'],
                    # Derived presentation layer metrics
                    'steep_5pct_distance_m': accessibility['steep_5pct_distance_m'],
                    'steep_5pct_route_percentage': accessibility['steep_5pct_route_percentage'],
                    'steep_5pct_continuous_stretches': accessibility['steep_5pct_continuous_stretches'],
                    'steep_5pct_avg_stretch_length_m': accessibility['steep_5pct_avg_stretch_length_m'],
                    'steep_5pct_longest_stretch_m': accessibility['steep_5pct_longest_stretch_m'],
                    'steep_8pct_distance_m': accessibility['steep_8pct_distance_m'],
                    'steep_8pct_route_percentage': accessibility['steep_8pct_route_percentage'],
                    'steep_8pct_continuous_stretches': accessibility['steep_8pct_continuous_stretches'],
                    'steep_8pct_avg_stretch_length_m': accessibility['steep_8pct_avg_stretch_length_m'],
                    'steep_8pct_longest_stretch_m': accessibility['steep_8pct_longest_stretch_m'],
                    'api_validation_avg_diff_m': validation['avg_difference'] if validation else None,
                    'api_validation_max_diff_m': validation['max_difference'] if validation else None,
                    'api_validation_points': validation['validation_points'] if validation else None,
                    'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                category_results.append(result)
                
                print(f"    ✅ Complete: {gpx_data['elevation_coverage']:.1f}% elevation coverage")
                print(f"       Range: {result['min_elevation_m']:.1f}m to {result['max_elevation_m']:.1f}m")
                print(f"       Accessibility: {accessibility['accessibility_rating']}")
                if validation:
                    print(f"       API validation: ±{validation['avg_difference']:.1f}m avg difference")
            
            all_results[category] = category_results
        
        return all_results
    
    def save_elevation_tables(self, results):
        """Save elevation analysis results to Excel files"""
        output_dir = os.path.join('..', 'Aggregated_Data')
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        for category, data in results.items():
            if not data:
                continue
            
            df = pd.DataFrame(data)
            
            # Generate filename
            if category == 'parkrun':
                filename = 'Parkrun_elevation.xlsx'
            elif category == 'events_2026':
                filename = 'Events_2026_elevation.xlsx'
            elif category == 'events_2027':
                filename = 'Events_2027_elevation.xlsx'
            else:
                filename = f'{category}_elevation.xlsx'
            
            output_path = os.path.join(output_dir, filename)
            
            try:
                df.to_excel(output_path, index=False)
                print(f"💾 Saved: {output_path}")
                print(f"   📊 {len(data)} records")
            except Exception as e:
                print(f"❌ Error saving {output_path}: {e}")

    def print_human_readable_summary(self, results):
        """Print human-readable accessibility summaries"""
        for category, data in results.items():
            if not data:
                continue
                
            category_name = category.replace('_', ' ').upper()
            print(f"\n🏃 {category_name} ACCESSIBILITY SUMMARY")
            print("=" * 50)
            
            for result in data:
                filename = result['filename'].replace('_ENH.gpx', '')
                print(f"\n📍 {filename.upper()}")
                print(f"   Route: {result['total_distance_km']:.1f} km")
                print(f"   Accessibility: {result['accessibility_rating']}")
                
                # 5% gradient summary
                if result['steep_5pct_continuous_stretches'] > 0:
                    print(f"   Steep sections (≥5%): {result['steep_5pct_distance_m']:.0f}m total ({result['steep_5pct_route_percentage']:.1f}% of route)")
                    print(f"   Longest continuous climb above 5%: {result['steep_5pct_longest_stretch_m']:.0f} m")
                else:
                    print(f"   Steep sections (≥5%): None")
                
                # 8% gradient summary  
                if result['steep_8pct_continuous_stretches'] > 0:
                    print(f"   Very steep sections (≥8%): {result['steep_8pct_distance_m']:.0f}m total ({result['steep_8pct_route_percentage']:.1f}% of route)")
                    print(f"   Longest continuous climb above 8%: {result['steep_8pct_longest_stretch_m']:.0f} m")
                else:
                    print(f"   Very steep sections (≥8%): None")

def main():
    print("🏔️  ENHANCED ELEVATION ANALYSIS & VALIDATION SYSTEM")
    print("=" * 60)
    print("This will analyze all enhanced GPX files for:")
    print("• Elevation accuracy validation via API")
    print("• Gradient analysis and accessibility metrics") 
    print("• Comprehensive elevation data tables")
    print("• Cross-validation with external elevation data")
    
    analyzer = ElevationAnalyzer()
    
    # Process all enhanced GPX files
    results = analyzer.process_enhanced_gpx_files()
    
    # Save results to tables
    print(f"\n💾 Saving elevation analysis tables...")
    analyzer.save_elevation_tables(results)
    
    # Print human-readable summaries
    analyzer.print_human_readable_summary(results)
    
    # Summary
    print(f"\n📊 ANALYSIS COMPLETE")
    print(f"=" * 30)
    for category, data in results.items():
        if data:
            print(f"{category.upper()}: {len(data)} routes analyzed")
    
    print(f"\nℹ️  Elevation tables saved to Aggregated_Data/:")
    print(f"   📄 Parkrun_elevation.xlsx")
    print(f"   📄 Events_2026_elevation.xlsx") 
    print(f"   📄 Events_2027_elevation.xlsx")

if __name__ == "__main__":
    main()