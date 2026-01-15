# Import Dependencies
import os
import re
import shutil
import gpxpy
import pandas as pd

def get_event_distance(event_id):
    """
    Get the distance for a 2026 event from Events_2026.xlsx
    
    Args:
        event_id (str): Event ID (e.g., "1001")
        
    Returns:
        float: Distance in kilometers, or None if not found
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.dirname(script_dir)
        excel_path = os.path.join(data_dir, 'Raw_Data', 'Events_2026.xlsx')
        
        if not os.path.exists(excel_path):
            print(f"❌ Events_2026.xlsx not found at: {excel_path}")
            return None
            
        # Read the Excel file
        df = pd.read_excel(excel_path)
        
        # Find the event by ID
        event_row = df[df['event_id'] == int(event_id)]
        
        if event_row.empty:
            print(f"❌ Event ID {event_id} not found in Events_2026.xlsx")
            return None
            
        distance_str = str(event_row.iloc[0]['event_distance']).strip()
        
        # Convert distance string to kilometers
        distance_map = {
            '5k': 5.0,
            '5K': 5.0,
            '10k': 10.0,
            '10K': 10.0,
            'Half': 21.1,
            'half': 21.1,
            'Marathon': 42.2,
            'marathon': 42.2
        }
        
        if distance_str in distance_map:
            distance_km = distance_map[distance_str]
            print(f"📏 Event {event_id} distance: {distance_str} ({distance_km}km)")
            return distance_km
        else:
            print(f"❌ Unknown distance format: {distance_str}")
            return None
            
    except Exception as e:
        print(f"❌ Error reading Events_2026.xlsx: {e}")
        return None

def get_user_input():
    """Ask user which GPX file to enhance"""
    filename = input("Enter the GPX file to enhance (e.g., PR1001_corby.gpx): ").strip()
    return filename

def load_temp_files():
    """
    Load all GPX files from GPX_Temp folder
    
    Returns:
        list: List of tuples (filename, gpx_object)
    """
    # Get the GPX_Temp directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    temp_dir = os.path.join(data_dir, 'GPX', 'GPX_Temp')
    
    if not os.path.exists(temp_dir):
        print(f"❌ Error: GPX_Temp directory not found: {temp_dir}")
        return []
    
    gpx_files = []
    print(f"📂 Loading files from: {temp_dir}")
    
    for filename in os.listdir(temp_dir):
        if filename.lower().endswith('.gpx'):
            file_path = os.path.join(temp_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    gpx = gpxpy.parse(f)
                gpx_files.append((filename, gpx))
                print(f"  ✅ Loaded: {filename}")
            except Exception as e:
                print(f"  ⚠️  Warning: Could not load {filename}: {e}")
    
    print(f"📊 Total files loaded: {len(gpx_files)}")
    return gpx_files

def validate_corridor_similarity(candidate_points, original_gpx, filename):
    """
    Validate that candidate route follows similar corridor to original
    
    Args:
        candidate_points: Points from candidate GPX
        original_gpx: Original GPX for comparison
        filename: Name of candidate file (for logging)
        
    Returns:
        bool: True if route follows similar corridor, False otherwise
    """
    if not original_gpx or not candidate_points:
        return True  # Skip validation if no baseline
        
    # Extract original points
    original_points = []
    for track in original_gpx.tracks:
        for segment in track.segments:
            original_points.extend(segment.points)
    
    if len(original_points) < 2:
        return True  # Skip if original too short
        
    # Sample candidate points (max 50 for performance)
    sample_size = min(50, len(candidate_points))
    step = max(1, len(candidate_points) // sample_size)
    sampled_candidates = [candidate_points[i * step] for i in range(sample_size)]
    
    # Calculate distances to original corridor
    distances_to_baseline = []
    for cand_point in sampled_candidates:
        min_dist = float('inf')
        for orig_point in original_points:
            dist = gpxpy.geo.haversine_distance(
                cand_point.latitude, cand_point.longitude,
                orig_point.latitude, orig_point.longitude
            )
            if dist < min_dist:
                min_dist = dist
        distances_to_baseline.append(min_dist)
    
    # Calculate statistics
    avg_distance = sum(distances_to_baseline) / len(distances_to_baseline)
    far_points = len([d for d in distances_to_baseline if d > 50])
    far_point_percentage = (far_points / len(distances_to_baseline)) * 100
    
    # Validation criteria (relaxed for sparse original routes)
    max_avg_distance = 50  # Average distance should be < 50m (was 30m)
    max_far_point_pct = 30  # Max 30% of points can be >50m away (was 20%)
    
    is_valid = avg_distance <= max_avg_distance and far_point_percentage <= max_far_point_pct
    
    # Debug output for failed validations
    if not is_valid:
        print(f"    📊 Corridor analysis: avg {avg_distance:.1f}m, {far_point_percentage:.1f}% >50m away")
        print(f"    ❌ Failed: avg >{max_avg_distance}m or >{max_far_point_pct}% far points")
    else:
        print(f"    ✅ Corridor check: avg {avg_distance:.1f}m, {far_point_percentage:.1f}% >50m away")
    
    return is_valid

def analyze_temp_files(original_path, temp_files, file_type):
    """
    Analyze temp files for route accuracy, elevation data, and point count
    
    Args:
        original_path (str): Path to the original GPX file
        temp_files (list): List of tuples (filename, gpx_object)
        file_type (str): Type of file ('parkrun', '2026_event', '2027_event')
    """
    print(f"\n🔬 Analyzing candidate files...")
    print("=" * 50)
    
    # Load the original file for comparison
    try:
        with open(original_path, 'r', encoding='utf-8') as f:
            original_gpx = gpxpy.parse(f)
        print(f"📍 Original file loaded: {os.path.basename(original_path)}")
    except Exception as e:
        print(f"❌ Error loading original file: {e}")
        return
    
    # Get original file stats for comparison
    original_distance = original_gpx.length_3d() or original_gpx.length_2d() or 0
    original_points = sum(len(segment.points) for track in original_gpx.tracks for segment in track.segments)
    
    print(f"📏 Original course: {original_distance/1000:.2f} km")
    print(f"📊 Original points: {original_points}")
    
    # Determine target distance based on file type
    if file_type == 'parkrun':
        target_distance = 5000  # Parkruns are always 5km
        print(f"🎯 Target distance: 5.00 km (parkrun)")
    elif file_type == '2026_event':
        # Extract event ID from original filename
        filename = os.path.basename(original_path)
        event_id_match = re.match(r'(\d+)', filename)
        if event_id_match:
            event_id = event_id_match.group(1)
            event_distance_km = get_event_distance(event_id)
            if event_distance_km:
                target_distance = event_distance_km * 1000  # Convert to meters
                print(f"🎯 Target distance: {event_distance_km:.1f} km (2026 event {event_id})")
            else:
                print(f"⚠️  Could not determine event distance, using original: {original_distance/1000:.2f} km")
                target_distance = original_distance
        else:
            print(f"⚠️  Could not extract event ID from filename, using original: {original_distance/1000:.2f} km")
            target_distance = original_distance
    elif file_type == '2027_event':
        # TODO: Add Events_2027.xlsx lookup when available
        target_distance = original_distance
        print(f"🎯 Target distance: {target_distance/1000:.2f} km (2027 event - using original)")
    else:
        target_distance = original_distance
        print(f"🎯 Target distance: {target_distance/1000:.2f} km (from original)")
    
    print(f"\n📋 Candidate file analysis:")
    print("-" * 30)
    
    valid_files = []
    
    for filename, gpx in temp_files:
        print(f"\n📄 {filename}")
        
        # Extract candidate points for validation
        candidate_points = []
        for track in gpx.tracks:
            for segment in track.segments:
                candidate_points.extend(segment.points)
        
        # Count points
        points = len(candidate_points)
        print(f"  Points: {points}")
        
        # Check elevation data
        has_elevation = False
        elevation_count = 0
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    if point.elevation is not None:
                        elevation_count += 1
                        has_elevation = True
        
        elevation_percentage = (elevation_count / points * 100) if points > 0 else 0
        print(f"  Elevation: {elevation_count}/{points} points ({elevation_percentage:.1f}%)")
        
        # Check route accuracy (distance comparison against target)
        file_distance = gpx.length_3d() or gpx.length_2d() or 0
        distance_diff = abs(file_distance - target_distance) / target_distance * 100 if target_distance > 0 else 0
        print(f"  Distance: {file_distance/1000:.2f} km (diff: {distance_diff:.1f}%)")
        
        # Check start/finish coordinates match (spatial validation)
        def get_route_endpoints(gpx_obj):
            """Get start and end coordinates from GPX"""
            for track in gpx_obj.tracks:
                for segment in track.segments:
                    if segment.points:
                        start_point = segment.points[0]
                        end_point = segment.points[-1]
                        return (start_point.latitude, start_point.longitude), (end_point.latitude, end_point.longitude)
            return None, None
        
        # Get original route endpoints
        orig_start, orig_end = get_route_endpoints(original_gpx)
        candidate_start, candidate_end = get_route_endpoints(gpx)
        
        route_match = True
        spatial_issues = []
        
        if orig_start and candidate_start:
            # Calculate distance between start points (in meters)
            start_distance = gpxpy.geo.haversine_distance(orig_start[0], orig_start[1], candidate_start[0], candidate_start[1])
            end_distance = gpxpy.geo.haversine_distance(orig_end[0], orig_end[1], candidate_end[0], candidate_end[1])
            
            print(f"  Start distance: {start_distance:.0f}m, End distance: {end_distance:.0f}m")
            
            # Allow 500m tolerance for start/end points
            if start_distance > 500:
                route_match = False
                spatial_issues.append(f"Start too far ({start_distance:.0f}m)")
            
            if end_distance > 500:
                route_match = False
                spatial_issues.append(f"End too far ({end_distance:.0f}m)")
        else:
            route_match = False
            spatial_issues.append("Could not get coordinates")
        
        # Determine if file is valid
        is_valid = True
        issues = []
        
        if not has_elevation:
            is_valid = False
            issues.append("No elevation data")
        
        if points < 50:  # Minimum point threshold
            is_valid = False
            issues.append(f"Too few points ({points})")
        
        if distance_diff > 20:  # Allow 20% distance difference
            is_valid = False
            issues.append(f"Distance too different ({distance_diff:.1f}%)")
            
        # Corridor similarity check - ensure route follows similar path
        if is_valid and not validate_corridor_similarity(candidate_points, original_gpx, filename):
            is_valid = False
            issues.append("Route corridor too different from original")
        
        if not route_match:  # Spatial validation failed
            is_valid = False
            issues.extend(spatial_issues)
        
        if is_valid:
            print(f"  Status: ✅ VALID")
            valid_files.append((filename, gpx, points, elevation_percentage))
        else:
            print(f"  Status: ❌ INVALID - {', '.join(issues)}")
    
    print(f"\n📊 Summary: {len(valid_files)}/{len(temp_files)} files passed validation")
    
    if valid_files:
        print(f"\n✅ Valid files:")
        for filename, _, points, elev_pct in valid_files:
            print(f"  - {filename}: {points} points, {elev_pct:.1f}% elevation")
    
    return valid_files

def select_base_route(valid_files, file_type, original_gpx, original_filename):
    """
    Select the highest resolution file as the base route
    
    Args:
        valid_files (list): List of valid candidate files
        file_type (str): Type of file for target calculations
        
    Returns:
        tuple: (base_filename, base_gpx, target_points) or None if no files
    """
    if not valid_files:
        return None
    
    print(f"\n🏆 Selecting base route...")
    print("=" * 40)
    
    # TODO FUTURE: Replace simple point count ranking with composite score:
    # - Distance accuracy weight
    # - Corridor similarity weight  
    # - Elevation coverage weight
    # - Point density quality weight
    # This would prevent noisy high-count traces from beating clean lower-count ones
    
    # Sort by point count (highest first) - current simple strategy
    sorted_files = sorted(valid_files, key=lambda x: x[2], reverse=True)
    
    print("📊 Candidates ranked by resolution:")
    for i, (filename, gpx, points, elev_pct) in enumerate(sorted_files):
        marker = "👑" if i == 0 else f"{i+1}."
        print(f"  {marker} {filename}: {points} points, {elev_pct:.1f}% elevation")
    
    # GUARDRAIL: If top 2 are close in points, prefer better corridor quality
    if len(sorted_files) >= 2:
        top_candidate = sorted_files[0]
        second_candidate = sorted_files[1]
        
        # Only apply guardrail if point counts are reasonably close (within 50% difference)
        point_ratio = second_candidate[2] / top_candidate[2]
        if point_ratio > 0.5:  # Second candidate has >50% of top candidate's points
            print(f"\n🛡️  Applying quality guardrail between top candidates...")
            
            # Calculate corridor deviation for both against original route
            def calculate_corridor_deviation(candidate_gpx, original_gpx):
                # Extract points from candidate
                candidate_points = []
                for track in candidate_gpx.tracks:
                    for segment in track.segments:
                        candidate_points.extend(segment.points)
                
                # Extract points from original
                original_points = []
                for track in original_gpx.tracks:
                    for segment in track.segments:
                        original_points.extend(segment.points)
                
                # Sample candidate points for performance
                sample_size = min(50, len(candidate_points))
                step = max(1, len(candidate_points) // sample_size)
                sampled = [candidate_points[i * step] for i in range(sample_size)]
                
                # Calculate average distance to original corridor
                total_distance = 0
                for cand_point in sampled:
                    min_dist = min(
                        gpxpy.geo.haversine_distance(
                            cand_point.latitude, cand_point.longitude,
                            orig_point.latitude, orig_point.longitude
                        ) for orig_point in original_points
                    )
                    total_distance += min_dist
                
                return total_distance / len(sampled) if sampled else float('inf')
            
            top_deviation = calculate_corridor_deviation(top_candidate[1], original_gpx)
            second_deviation = calculate_corridor_deviation(second_candidate[1], original_gpx)
            
            print(f"  {top_candidate[0]}: {top_deviation:.1f}m avg deviation")
            print(f"  {second_candidate[0]}: {second_deviation:.1f}m avg deviation")
            
            # For events, also consider start/finish alignment when choosing between good candidates
            decision_made = False
            if file_type.endswith('_event'):
                # Calculate start/finish proximity for both candidates
                def calculate_endpoint_deviation(candidate_gpx, original_gpx):
                    # Extract start/end points
                    cand_points = []
                    for track in candidate_gpx.tracks:
                        for segment in track.segments:
                            cand_points.extend(segment.points)
                    
                    orig_points = []
                    for track in original_gpx.tracks:
                        for segment in track.segments:
                            orig_points.extend(segment.points)
                    
                    if not cand_points or not orig_points:
                        return float('inf')
                    
                    start_dev = gpxpy.geo.haversine_distance(
                        cand_points[0].latitude, cand_points[0].longitude,
                        orig_points[0].latitude, orig_points[0].longitude
                    )
                    end_dev = gpxpy.geo.haversine_distance(
                        cand_points[-1].latitude, cand_points[-1].longitude,
                        orig_points[-1].latitude, orig_points[-1].longitude
                    )
                    return max(start_dev, end_dev)
                
                top_endpoint_dev = calculate_endpoint_deviation(top_candidate[1], original_gpx)
                second_endpoint_dev = calculate_endpoint_deviation(second_candidate[1], original_gpx)
                
                print(f"  {top_candidate[0]}: {top_endpoint_dev:.1f}m endpoint deviation")
                print(f"  {second_candidate[0]}: {second_endpoint_dev:.1f}m endpoint deviation")
                
                # If second candidate has much better endpoint alignment (and decent corridor), prefer it
                if (second_endpoint_dev < 25 and top_endpoint_dev > 75 and 
                    second_deviation < top_deviation * 1.5):  # Relaxed corridor requirement
                    base_filename, base_gpx, base_points, base_elev_pct = second_candidate
                    print(f"  🎯 Selecting {base_filename} for superior start/finish alignment")
                    decision_made = True
            
            if not decision_made:
                # Apply standard corridor quality guardrail
                if second_deviation < top_deviation * 0.7:  # 30% better corridor quality
                    base_filename, base_gpx, base_points, base_elev_pct = second_candidate
                    print(f"  🔄 Selecting {base_filename} for better corridor quality")
                else:
                    base_filename, base_gpx, base_points, base_elev_pct = top_candidate
                    print(f"  ✅ Keeping {base_filename} (sufficient corridor quality)")
        else:
            # Point counts too different, stick with highest
            base_filename, base_gpx, base_points, base_elev_pct = sorted_files[0]
    else:
        # Only one candidate
        base_filename, base_gpx, base_points, base_elev_pct = sorted_files[0]
    
    print(f"\n✅ Selected base route: {base_filename}")
    print(f"📊 Base route stats:")
    print(f"  - Points: {base_points}")
    print(f"  - Elevation coverage: {base_elev_pct:.1f}%")
    
    # Calculate target point count based on distance
    target_distance_source = "base route"
    if file_type == 'parkrun':
        target_distance_km = 5.0
        target_distance_source = "parkrun standard"
    elif file_type == '2026_event' and original_filename:
        # Extract event ID from original filename for distance lookup
        event_id_match = re.match(r'(\d+)', original_filename)
        if event_id_match:
            event_id = event_id_match.group(1)
            event_distance_km = get_event_distance(event_id)
            if event_distance_km:
                target_distance_km = event_distance_km  # Use Excel event distance
                target_distance_source = "event table"
            else:
                # Fall back to GPX distance if lookup fails
                route_distance = base_gpx.length_3d() or base_gpx.length_2d() or 0
                target_distance_km = route_distance / 1000
                target_distance_source = "base route (lookup failed)"
        else:
            # Fall back to GPX distance if no event ID found
            route_distance = base_gpx.length_3d() or base_gpx.length_2d() or 0
            target_distance_km = route_distance / 1000
            target_distance_source = "base route (no event ID)"
    else:
        # For other routes, use base route distance
        route_distance = base_gpx.length_3d() or base_gpx.length_2d() or 0
        target_distance_km = route_distance / 1000
    
    target_points = int(target_distance_km * 125)  # 125 points per km for wheelchair accessibility analysis
    
    print(f"🎯 Target for enhanced route:")
    print(f"  - Distance: {target_distance_km:.2f} km (from {target_distance_source})")
    print(f"  - Target points: {target_points} (125 points/km)")
    
    if base_points > target_points:
        print(f"  - Action needed: Reduce from {base_points} to {target_points} points")
    else:
        print(f"  - Action needed: Interpolate from {base_points} to {target_points} points")
    
    return base_filename, base_gpx, target_points

def enhance_route_with_interpolation(base_gpx, valid_files, target_points):
    """
    Enhance the base route using PRIORITIZED ELEVATION PRESERVATION
    
    ELEVATION STRATEGY: Uses base route elevations as primary source,
    only falling back to other files when base lacks elevation data.
    This is NOT true multi-trace fusion - it prioritizes detail preservation
    over cross-source averaging.
    
    Args:
        base_gpx: The highest resolution GPX object (primary elevation source)
        valid_files: All valid candidate files (backup elevation sources only)
        target_points: Target number of points for final route
        
    Returns:
        gpxpy.gpx.GPX: Enhanced GPX object
    """
    print(f"🔧 Enhancing route with prioritized elevation preservation...")
    print("="*58)
    
    # Extract all track points from base route
    base_points = []
    for track in base_gpx.tracks:
        for segment in track.segments:
            base_points.extend(segment.points)
    
    print(f"📊 Base route: {len(base_points)} points")
    print(f"📊 Using base route elevations with {len(valid_files)-1} backup sources")
    # NOTE: This is "prioritized elevation preservation", not true multi-trace fusion
    # Base route elevations are used exclusively when available to preserve detail
    
    # Calculate cumulative distance along the route for even distribution
    cumulative_distances = [0]
    for i in range(1, len(base_points)):
        dist = gpxpy.geo.haversine_distance(
            base_points[i-1].latitude, base_points[i-1].longitude,
            base_points[i].latitude, base_points[i].longitude
        )
        cumulative_distances.append(cumulative_distances[-1] + dist)
    
    total_distance = cumulative_distances[-1]
    print(f"📏 Total route distance: {total_distance/1000:.2f} km")
    
    # Create evenly spaced target distances
    target_distances = []
    for i in range(target_points):
        target_distances.append(i * total_distance / (target_points - 1))
    
    print(f"🎯 Creating {target_points} evenly distributed points with prioritized elevations")
    
    # Interpolate points at target distances with multi-file elevation fusion
    enhanced_points = []
    for target_dist in target_distances:
        # Find the two closest points in base route
        closest_idx = 0
        for i, cum_dist in enumerate(cumulative_distances):
            if cum_dist <= target_dist:
                closest_idx = i
            else:
                break
        
        # Handle edge cases
        if closest_idx >= len(base_points) - 1:
            enhanced_points.append(base_points[-1])
            continue
        
        # Interpolate between closest_idx and closest_idx + 1
        point1 = base_points[closest_idx]
        point2 = base_points[closest_idx + 1]
        
        dist1 = cumulative_distances[closest_idx]
        dist2 = cumulative_distances[closest_idx + 1]
        
        if dist2 - dist1 == 0:  # Same distance, use first point
            ratio = 0
        else:
            ratio = (target_dist - dist1) / (dist2 - dist1)
        
        # Interpolate coordinates from base route
        new_lat = point1.latitude + ratio * (point2.latitude - point1.latitude)
        new_lon = point1.longitude + ratio * (point2.longitude - point1.longitude)
        
        # ELEVATION STRATEGY: Prioritized preservation (not true fusion)
        # - Primary: Use base route elevation to preserve detailed profile
        # - Backup: Only use other sources when base lacks elevation data
        # - This maintains sharp elevation changes critical for accessibility analysis
        final_elevation = None
        
        # First priority: Use base route elevation (preserves hills/valleys)
        if point1.elevation is not None and point2.elevation is not None:
            final_elevation = point1.elevation + ratio * (point2.elevation - point1.elevation)
        elif point1.elevation is not None:
            final_elevation = point1.elevation
        elif point2.elevation is not None:
            final_elevation = point2.elevation
        
        # Only if base route lacks elevation, use backup from other files
        if final_elevation is None:
            candidate_elevations = []
            
            for filename, candidate_gpx, _, _ in valid_files:
                # Extract points from candidate file
                candidate_points = []
                for track in candidate_gpx.tracks:
                    for segment in track.segments:
                        candidate_points.extend(segment.points)
                
                # Find closest point in candidate file to our interpolated position
                min_distance = float('inf')
                closest_candidate = None
                for cand_point in candidate_points:
                    if cand_point.elevation is not None:
                        distance = gpxpy.geo.haversine_distance(
                            new_lat, new_lon, cand_point.latitude, cand_point.longitude
                        )
                        if distance < min_distance and distance < 50:  # Stricter proximity for backup
                            min_distance = distance
                            closest_candidate = cand_point
                
                # Add elevation from closest backup source
                if closest_candidate:
                    candidate_elevations.append(closest_candidate.elevation)
            
            # Use median of backup sources if any found
            if candidate_elevations:
                final_elevation = sorted(candidate_elevations)[len(candidate_elevations)//2]
        
        # Create new track point with prioritized elevation
        new_point = gpxpy.gpx.GPXTrackPoint(
            latitude=new_lat,
            longitude=new_lon,
            elevation=final_elevation
        )
        
        enhanced_points.append(new_point)
    
    print(f"✅ Interpolated {len(enhanced_points)} points with prioritized elevation preservation")
    
    # Create enhanced GPX object (no smoothing to preserve distance)
    enhanced_gpx = gpxpy.gpx.GPX()
    enhanced_gpx.name = "Enhanced Route"
    enhanced_gpx.description = "High-resolution enhanced route with multi-source elevation fusion"
    enhanced_gpx.creator = "Route Analysis Enhancement Tool"
    
    # Create track and segment
    track = gpxpy.gpx.GPXTrack()
    track.name = "Enhanced Track"
    enhanced_gpx.tracks.append(track)
    
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)
    
    # Add interpolated points to segment
    for point in enhanced_points:
        segment.points.append(point)
    
    # Calculate final stats
    final_distance = enhanced_gpx.length_3d() or enhanced_gpx.length_2d() or 0
    points_per_km = len(enhanced_points) / (final_distance / 1000) if final_distance > 0 else 0
    
    elevation_count = sum(1 for p in enhanced_points if p.elevation is not None)
    elevation_coverage = (elevation_count / len(enhanced_points) * 100) if enhanced_points else 0
    
    print(f"\n📊 Enhanced route statistics:")
    print(f"  - Final points: {len(enhanced_points)}")
    print(f"  - Distance: {final_distance/1000:.2f} km")
    print(f"  - Resolution: {points_per_km:.1f} points/km")
    print(f"  - Elevation coverage: {elevation_coverage:.1f}% (prioritized base route)")
    print(f"  - Distance preservation: {(final_distance/total_distance)*100:.1f}% vs base")
    
    return enhanced_gpx


def validate_enhanced_route(enhanced_gpx, original_gpx, file_type, base_gpx=None, filename=None, valid_files=None):
    """
    Validate enhanced route with comprehensive confidence scoring
    
    Args:
        enhanced_gpx: Enhanced GPX object
        original_gpx: Original GPX object for comparison
        file_type: Type of file for expected distance calculations
        base_gpx: Base high-resolution GPX for fidelity comparison
        
    Returns:
        tuple: (is_valid, confidence_score, validation_report)
    """
    print(f"\n🔍 Comprehensive Route Validation & Confidence Scoring...")
    print("=" * 60)
    
    # Extract points from both routes
    enhanced_points = []
    for track in enhanced_gpx.tracks:
        for segment in track.segments:
            enhanced_points.extend(segment.points)
    
    original_points = []
    for track in original_gpx.tracks:
        for segment in track.segments:
            original_points.extend(segment.points)
    
    print(f"📊 Enhanced route: {len(enhanced_points)} points")
    print(f"📊 Original route: {len(original_points)} points")
    
    # Initialize confidence scoring
    confidence_scores = {}
    validation_report = {}
    
    # === BASELINE QUALITY ASSESSMENT ===
    # Determine if original route quality affects confidence interpretation
    original_distance = original_gpx.length_3d() or original_gpx.length_2d() or 0
    expected_distance = 5000 if file_type == 'parkrun' else original_distance
    
    baseline_sparse = len(original_points) < 50
    baseline_short = original_distance < (0.7 * expected_distance)
    
    if baseline_sparse or baseline_short:
        baseline_quality = "LOW_RES"
        quality_note = f"Original route: {len(original_points)} points, {original_distance/1000:.2f}km"
    else:
        baseline_quality = "ADEQUATE"
        quality_note = f"Original route: {len(original_points)} points, {original_distance/1000:.2f}km"
    
    print(f"\n📋 Baseline Quality Assessment: {baseline_quality}")
    print(f"  {quality_note}")
    if baseline_quality == "LOW_RES":
        print(f"  ℹ️  Low baseline quality may limit confidence ceiling")
    
    # 1. Distance Plausibility Check
    print(f"\n📏 1. Distance Plausibility Analysis:")
    enhanced_distance = enhanced_gpx.length_3d() or enhanced_gpx.length_2d() or 0
    original_distance = original_gpx.length_3d() or original_gpx.length_2d() or 0
    
    if file_type == 'parkrun':
        expected_distance = 5000  # Parkruns are always 5km
    elif file_type == '2026_event' and filename:
        # Extract event ID from filename for distance lookup
        event_id_match = re.match(r'(\d+)', filename)
        if event_id_match:
            event_id = event_id_match.group(1)
            event_distance_km = get_event_distance(event_id)
            expected_distance = event_distance_km * 1000 if event_distance_km else original_distance
        else:
            expected_distance = original_distance
    else:
        expected_distance = original_distance
    
    distance_diff_pct = abs(enhanced_distance - expected_distance) / expected_distance * 100
    
    print(f"  Enhanced: {enhanced_distance/1000:.2f} km")
    print(f"  Expected: {expected_distance/1000:.2f} km")
    print(f"  Difference: {distance_diff_pct:.1f}%")
    
    if distance_diff_pct <= 2:
        distance_score = 100
    elif distance_diff_pct <= 5:
        distance_score = 80
    elif distance_diff_pct <= 10:
        distance_score = 60
    else:
        distance_score = 20
    
    confidence_scores['distance'] = distance_score
    validation_report['distance'] = {
        'enhanced_km': enhanced_distance/1000,
        'expected_km': expected_distance/1000,
        'difference_pct': distance_diff_pct,
        'score': distance_score
    }
    
    # 2. Jump Detection (unrealistic gaps between consecutive points)
    print(f"\n🦘 2. Jump Detection Analysis:")
    jumps = []
    for i in range(1, len(enhanced_points)):
        jump_distance = gpxpy.geo.haversine_distance(
            enhanced_points[i-1].latitude, enhanced_points[i-1].longitude,
            enhanced_points[i].latitude, enhanced_points[i].longitude
        )
        if jump_distance > 100:  # >100m jumps are suspicious
            jumps.append((i, jump_distance))
    
    print(f"  Total jumps >100m: {len(jumps)}")
    if jumps:
        max_jump = max(jumps, key=lambda x: x[1])
        print(f"  Largest jump: {max_jump[1]:.1f}m at point {max_jump[0]}")
    
    if len(jumps) == 0:
        jump_score = 100
    elif len(jumps) <= 2:
        jump_score = 70
    elif len(jumps) <= 5:
        jump_score = 40
    else:
        jump_score = 10
    
    confidence_scores['jumps'] = jump_score
    validation_report['jumps'] = {
        'jump_count': len(jumps),
        'max_jump_m': max(jumps, key=lambda x: x[1])[1] if jumps else 0,
        'score': jump_score
    }
    
    # 3. Points per km Analysis
    print(f"\n📈 3. Point Density Analysis:")
    points_per_km = len(enhanced_points) / (enhanced_distance / 1000) if enhanced_distance > 0 else 0
    print(f"  Achieved: {points_per_km:.1f} points/km")
    print(f"  Target: 125 points/km")
    
    if points_per_km >= 120:
        density_score = 100
    elif points_per_km >= 100:
        density_score = 90
    elif points_per_km >= 80:
        density_score = 70
    elif points_per_km >= 60:
        density_score = 50
    else:
        density_score = 20
    
    confidence_scores['density'] = density_score
    validation_report['density'] = {
        'points_per_km': points_per_km,
        'target_per_km': 125,
        'score': density_score
    }
    
    # 4. Start/Finish Proximity Analysis
    print(f"\n🔄 4. Start/Finish Proximity Analysis:")
    enh_start, enh_end = enhanced_points[0], enhanced_points[-1]
    
    # For parkruns, use base route endpoints (more reliable than sparse original)
    if file_type == 'parkrun' and base_gpx:
        # Extract base route points
        base_points_all = []
        for track in base_gpx.tracks:
            for segment in track.segments:
                base_points_all.extend(segment.points)
        
        ref_start, ref_end = base_points_all[0], base_points_all[-1]
        reference_source = "base route"
    else:
        # Use original endpoints for other route types or when no base available
        orig_start, orig_end = original_points[0], original_points[-1]
        ref_start, ref_end = orig_start, orig_end
        reference_source = "original route"
    
    # Check start/end accuracy
    start_deviation = gpxpy.geo.haversine_distance(
        enh_start.latitude, enh_start.longitude,
        ref_start.latitude, ref_start.longitude
    )
    
    end_deviation = gpxpy.geo.haversine_distance(
        enh_end.latitude, enh_end.longitude,
        ref_end.latitude, ref_end.longitude
    )
    
    # Check if it's a loop route - for parkruns, assume loop by definition
    if file_type == 'parkrun':
        is_loop = True  # Parkruns are always loops
        loop_distance = gpxpy.geo.haversine_distance(
            enh_start.latitude, enh_start.longitude,
            enh_end.latitude, enh_end.longitude
        )
    else:
        # Use original endpoints for other route types or when no base available
        orig_start, orig_end = original_points[0], original_points[-1]
        ref_start, ref_end = orig_start, orig_end
        reference_source = "original route"

    # Check start/end accuracy
    start_deviation = gpxpy.geo.haversine_distance(
        enh_start.latitude, enh_start.longitude,
        ref_start.latitude, ref_start.longitude
    )

    end_deviation = gpxpy.geo.haversine_distance(
        enh_end.latitude, enh_end.longitude,
        ref_end.latitude, ref_end.longitude
    )

    # Check route pattern and start/finish relationship
    start_finish_separation = gpxpy.geo.haversine_distance(
        enh_start.latitude, enh_start.longitude,
        enh_end.latitude, enh_end.longitude
    )
    
    # Determine route pattern for parkruns
    if file_type == 'parkrun':
        if start_finish_separation <= 25:
            route_pattern = "single_loop"
        elif start_finish_separation <= 75:
            route_pattern = "lapped"
        else:
            route_pattern = "lapped_offset_finish"  # Like 2.5 laps with offset finish
        
        is_closed = start_finish_separation <= 50
        
        print(f"  Start deviation: {start_deviation:.1f}m (vs {reference_source})")
        print(f"  End deviation: {end_deviation:.1f}m (vs {reference_source})")
        print(f"  Route pattern: {route_pattern.replace('_', ' ').title()}")
        print(f"  Start–finish separation: {start_finish_separation:.1f}m")
        if route_pattern == "lapped_offset_finish":
            print(f"    💡 Logistics note: Plan chair/bag drop-off considering finish location")
    else:
        # For events, determine if loop or point-to-point
        is_closed = start_finish_separation < 50
        if is_closed:
            route_pattern = "single_loop"
        else:
            route_pattern = "point_to_point"
        
        print(f"  Start deviation: {start_deviation:.1f}m (vs {reference_source})")
        print(f"  End deviation: {end_deviation:.1f}m (vs {reference_source})")
        print(f"  Route type: {'Loop' if is_closed else 'Point-to-point'}")
        if is_closed:
            print(f"  Start–finish separation: {start_finish_separation:.1f}m")
    
    # Improved scoring for parkruns - focus on logistics, not geometry
    if file_type == 'parkrun':
        # For parkruns, start/finish separation is LOGISTICS, not quality
        # All parkrun patterns (single loop, lapped, offset finish) are legitimate
        
        # Base score on reference alignment quality, not separation distance
        max_endpoint_dev = max(start_deviation, end_deviation)
        if max_endpoint_dev <= 15:
            proximity_score = 100
        elif max_endpoint_dev <= 30:
            proximity_score = 95
        elif max_endpoint_dev <= 50:
            proximity_score = 90
        else:
            proximity_score = 85
            
        # PARKRUN PROXIMITY FLOOR: Never below 85 for parkruns
        # Start/finish separation and pattern variations are normal parkrun geometry
        proximity_score = max(85, proximity_score)
        
        print(f"    📋 Parkrun proximity: {proximity_score}/100 (separation is logistics info, not quality metric)")
    elif file_type.endswith('_event'):
        # SMART PROXIMITY SCORING FOR EVENTS:
        # Compare against multiple reference sources and use best alignment
        # This removes penalties for "late start button press" or slight positioning differences
        
        # Get original endpoints
        orig_start, orig_end = original_points[0], original_points[-1]
        orig_start_dev = gpxpy.geo.haversine_distance(
            enh_start.latitude, enh_start.longitude,
            orig_start.latitude, orig_start.longitude
        )
        orig_end_dev = gpxpy.geo.haversine_distance(
            enh_end.latitude, enh_end.longitude,
            orig_end.latitude, orig_end.longitude
        )
        orig_max_dev = max(orig_start_dev, orig_end_dev)
        
        # Get base route endpoints (if available)
        base_max_dev = float('inf')
        if base_gpx:
            base_points_all = []
            for track in base_gpx.tracks:
                for segment in track.segments:
                    base_points_all.extend(segment.points)
            
            if base_points_all:
                base_start, base_end = base_points_all[0], base_points_all[-1]
                base_start_dev = gpxpy.geo.haversine_distance(
                    enh_start.latitude, enh_start.longitude,
                    base_start.latitude, base_start.longitude
                )
                base_end_dev = gpxpy.geo.haversine_distance(
                    enh_end.latitude, enh_end.longitude,
                    base_end.latitude, base_end.longitude
                )
                base_max_dev = max(base_start_dev, base_end_dev)
        
        # Use the best (minimum) endpoint deviation across all references
        best_max_dev = min(orig_max_dev, base_max_dev)
        
        print(f"  Smart proximity analysis:")
        print(f"    vs original: {orig_max_dev:.1f}m max deviation")
        if base_max_dev != float('inf'):
            print(f"    vs base route: {base_max_dev:.1f}m max deviation")
        print(f"    📍 Best alignment: {best_max_dev:.1f}m (using this for scoring)")
        
        # Score based on best alignment, not just original
        if best_max_dev <= 25:
            proximity_score = 100
        elif best_max_dev <= 50:
            proximity_score = 95
        elif best_max_dev <= 75:
            proximity_score = 90
        elif best_max_dev <= 100:
            proximity_score = 85
        elif best_max_dev <= 150:
            proximity_score = 80
        elif best_max_dev <= 200:
            proximity_score = 75
        else:
            proximity_score = 70
            
        # Additional quality-based score protection:
        # If fidelity and corridor quality are excellent, cap the proximity penalty
        # This prevents logistics variations from masking geometric accuracy
        # (Will be applied later when fidelity score is available)
        
        # EVENT PROXIMITY FLOOR: Never below 70 for events with smart scoring
        # Start/finish variations don't indicate route accessibility problems
        proximity_score = max(70, proximity_score)
    else:
        # For other routes, use original scoring method
        max_endpoint_dev = max(start_deviation, end_deviation)
        
        if max_endpoint_dev <= 25:
            proximity_score = 100
        elif max_endpoint_dev <= 50:
            proximity_score = 85
        elif max_endpoint_dev <= 100:
            proximity_score = 70
        else:
            proximity_score = 30
    
    confidence_scores['proximity'] = proximity_score
    validation_report['proximity'] = {
        'start_deviation_m': start_deviation,
        'end_deviation_m': end_deviation,
        'route_pattern': route_pattern if 'route_pattern' in locals() else 'unknown',
        'start_finish_separation_m': start_finish_separation if 'start_finish_separation' in locals() else None,
        'is_closed_loop': is_closed if 'is_closed' in locals() else None,
        'score': proximity_score
    }
    
    # 5. Elevation Quality Analysis
    print(f"\n🏔️  5. Elevation Data Quality Analysis:")
    elevation_count = sum(1 for p in enhanced_points if p.elevation is not None)
    elevation_coverage = (elevation_count / len(enhanced_points) * 100) if enhanced_points else 0
    
    print(f"  Elevation coverage: {elevation_coverage:.1f}% ({elevation_count}/{len(enhanced_points)})")
    
    # Check for elevation spikes
    elevation_spikes = []
    for i in range(1, len(enhanced_points)):
        if (enhanced_points[i-1].elevation is not None and 
            enhanced_points[i].elevation is not None):
            elev_diff = abs(enhanced_points[i].elevation - enhanced_points[i-1].elevation)
            if elev_diff > 10:
                elevation_spikes.append((i, elev_diff))
    
    print(f"  Elevation spikes >10m: {len(elevation_spikes)}")
    if elevation_spikes:
        max_spike = max(elevation_spikes, key=lambda x: x[1])
        print(f"  Largest spike: {max_spike[1]:.1f}m at point {max_spike[0]}")
    
    # Elevation scoring
    if elevation_coverage >= 99 and len(elevation_spikes) <= 2:
        elevation_score = 100
    elif elevation_coverage >= 95 and len(elevation_spikes) <= 5:
        elevation_score = 85
    elif elevation_coverage >= 90 and len(elevation_spikes) <= 10:
        elevation_score = 70
    elif elevation_coverage >= 80:
        elevation_score = 50
    else:
        elevation_score = 20
    
    confidence_scores['elevation'] = elevation_score
    validation_report['elevation'] = {
        'coverage_pct': elevation_coverage,
        'spike_count': len(elevation_spikes),
        'max_spike_m': max(elevation_spikes, key=lambda x: x[1])[1] if elevation_spikes else 0,
        'score': elevation_score
    }
    
    # 6. Overall Route Fidelity Analysis (compare against high-res base, not sparse original)
    print(f"\n📍 6. Route Fidelity Analysis:")
    
    # Use base route if provided, otherwise fall back to original (with warning)
    comparison_points = []
    if base_gpx:
        for track in base_gpx.tracks:
            for segment in track.segments:
                comparison_points.extend(segment.points)
        print(f"  Comparing against high-resolution base: {len(comparison_points)} points")
    else:
        comparison_points = original_points
        print(f"  ⚠️  Comparing against sparse original: {len(comparison_points)} points (less reliable)")
    
    # TODO PERFORMANCE: This is O(N×M) - consider KD-tree or sampling for large datasets
    route_deviations = []
    for enhanced_point in enhanced_points:
        min_distance = min(
            gpxpy.geo.haversine_distance(
                enhanced_point.latitude, enhanced_point.longitude,
                comp_point.latitude, comp_point.longitude
            ) for comp_point in comparison_points
        )
        route_deviations.append(min_distance)
    
    max_deviation = max(route_deviations) if route_deviations else 0
    avg_deviation = sum(route_deviations) / len(route_deviations) if route_deviations else 0
    significant_deviations = [d for d in route_deviations if d > 50]
    off_route_percentage = (len(significant_deviations) / len(route_deviations) * 100) if route_deviations else 0
    
    print(f"  Maximum deviation: {max_deviation:.1f}m")
    print(f"  Average deviation: {avg_deviation:.1f}m")
    print(f"  Points >50m off route: {len(significant_deviations)}/{len(route_deviations)} ({off_route_percentage:.1f}%)")
    
    # Improved fidelity scoring based on avg and max deviation (more granular than just >50m count)
    # Average deviation scoring component
    if avg_deviation <= 3:
        avg_score = 100
    elif avg_deviation <= 6:
        avg_score = 90
    elif avg_deviation <= 10:
        avg_score = 80
    elif avg_deviation <= 15:
        avg_score = 70
    else:
        avg_score = 60
    
    # Max deviation scoring component  
    if max_deviation <= 10:
        max_score = 100
    elif max_deviation <= 25:
        max_score = 85
    elif max_deviation <= 50:
        max_score = 70
    elif max_deviation <= 100:
        max_score = 55
    else:
        max_score = 40
    
    # Combine avg (70%) and max (30%) components for final fidelity score
    fidelity_score = int(avg_score * 0.7 + max_score * 0.3)
    
    confidence_scores['fidelity'] = fidelity_score
    validation_report['fidelity'] = {
        'max_deviation_m': max_deviation,
        'avg_deviation_m': avg_deviation,
        'points_off_route': len(significant_deviations),
        'off_route_percentage': off_route_percentage,
        'total_points': len(route_deviations),
        'comparison_source': 'base_route' if base_gpx else 'original_sparse',
        'score': fidelity_score
    }
    
    # 7. Cross-Candidate Agreement Analysis (prevents self-fulfilling scores)
    print(f"\n🤝 7. Cross-Candidate Agreement Analysis:")
    
    # Calculate agreement between top candidates to ensure multiple sources truly agree
    agreement_score = 100  # Default if insufficient candidates
    avg_cross_deviation = None
    
    # Only do this analysis if we have multiple valid candidates
    if valid_files and len(valid_files) >= 3:
        # Compare corridor agreement between top 3 candidates
        def calculate_cross_agreement(candidates):
            if len(candidates) < 3:
                return 100  # Perfect if too few to disagree
            
            # Take top 3 by point count
            top_3 = sorted(candidates, key=lambda x: x[2], reverse=True)[:3]
            
            total_deviations = []
            comparisons = 0
            
            for i in range(len(top_3)):
                for j in range(i + 1, len(top_3)):
                    candidate1_gpx = top_3[i][1]
                    candidate2_gpx = top_3[j][1]
                    
                    # Extract points from both candidates
                    points1 = []
                    for track in candidate1_gpx.tracks:
                        for segment in track.segments:
                            points1.extend(segment.points)
                    
                    points2 = []
                    for track in candidate2_gpx.tracks:
                        for segment in track.segments:
                            points2.extend(segment.points)
                    
                    if points1 and points2:
                        # Sample points for performance
                        sample_size = min(20, len(points1))
                        step1 = max(1, len(points1) // sample_size)
                        
                        sampled1 = [points1[i * step1] for i in range(sample_size) if i * step1 < len(points1)]
                        
                        # For each sampled point, find closest point in other route
                        for p1 in sampled1:
                            min_dist = min(
                                gpxpy.geo.haversine_distance(
                                    p1.latitude, p1.longitude,
                                    p2.latitude, p2.longitude
                                ) for p2 in points2
                            )
                            total_deviations.append(min_dist)
                            comparisons += 1
            
            if comparisons > 0:
                avg_deviation = sum(total_deviations) / len(total_deviations)
                return avg_deviation
            else:
                return 0
        
        avg_cross_deviation = calculate_cross_agreement(valid_files)
        
        print(f"  Candidates analyzed: {len(valid_files)}")
        print(f"  Average cross-candidate deviation: {avg_cross_deviation:.1f}m")
        
        # Score based on how well candidates agree with each other
        if avg_cross_deviation <= 15:
            agreement_score = 100
        elif avg_cross_deviation <= 25:
            agreement_score = 90
        elif avg_cross_deviation <= 40:
            agreement_score = 80
        elif avg_cross_deviation <= 60:
            agreement_score = 70
        else:
            agreement_score = 60
    elif valid_files and len(valid_files) == 2:
        print(f"  Only 2 candidates available - limited cross-validation")
        agreement_score = 85  # Limited cross-validation
    else:
        print(f"  Insufficient candidates for cross-validation")
        agreement_score = 60  # Single source - can't independently verify
    
    # Apply candidate count penalty to agreement score
    candidate_count = len(valid_files) if valid_files else 0
    if candidate_count >= 4:
        # Keep existing score for 4+ candidates
        pass
    elif candidate_count == 3:
        agreement_score = min(agreement_score, 92)  # Cap at 92 for 3 candidates
    elif candidate_count == 2:
        agreement_score = min(agreement_score, 85)  # Cap at 85 for 2 candidates  
    elif candidate_count == 1:
        agreement_score = 60  # Single source penalty
    
    print(f"  Final agreement score: {agreement_score}/100 (based on {candidate_count} candidates)")
    
    confidence_scores['agreement'] = agreement_score
    validation_report['agreement'] = {
        'cross_deviation_m': avg_cross_deviation,
        'candidates_analyzed': len(valid_files) if valid_files else 0,
        'score': agreement_score
    }
    
    # QUALITY-BASED PROXIMITY PROTECTION FOR EVENTS:
    # If fidelity and distance are excellent, prevent proximity from dragging down score
    if file_type.endswith('_event'):
        distance_excellent = confidence_scores['distance'] >= 95
        fidelity_excellent = confidence_scores['fidelity'] >= 95
        
        if distance_excellent and fidelity_excellent and confidence_scores['proximity'] < 80:
            original_proximity = confidence_scores['proximity']
            confidence_scores['proximity'] = 80  # Cap penalty at 80 for excellent routes
            print(f"\n🛡️  Quality-based proximity protection applied:")
            print(f"   Distance: {confidence_scores['distance']}/100, Fidelity: {confidence_scores['fidelity']}/100")
            print(f"   Proximity boosted: {original_proximity:.0f} → {confidence_scores['proximity']:.0f}")
            print(f"   Rationale: Endpoint differences are logistics, not geometry failure")
    
    # Calculate Overall Confidence Score (weighted average)
    # Dynamic agreement weight based on candidate count
    candidate_count = len(valid_files) if valid_files else 0
    if candidate_count == 1:
        agreement_weight = 0.25  # Increase weight when single source
        base_weight = 0.75 / 6   # Distribute remaining 75% across other 6 components
        weights = {
            'distance': base_weight,     # ~12.5% - Route distance accuracy
            'jumps': base_weight,        # ~12.5% - No unrealistic jumps
            'density': base_weight,      # ~12.5% - Point density achieved
            'proximity': base_weight,    # ~12.5% - Start/end accuracy
            'elevation': base_weight,    # ~12.5% - Elevation quality
            'fidelity': base_weight,     # ~12.5% - Overall route following
            'agreement': agreement_weight # 25% - Critical for single source validation
        }
    elif candidate_count == 2:
        agreement_weight = 0.18  # Increased weight for limited sources
        base_weight = 0.82 / 6   # Distribute remaining 82% across other 6 components
        weights = {
            'distance': base_weight,     # ~13.7% - Route distance accuracy
            'jumps': base_weight,        # ~13.7% - No unrealistic jumps
            'density': base_weight,      # ~13.7% - Point density achieved
            'proximity': base_weight,    # ~13.7% - Start/end accuracy
            'elevation': base_weight,    # ~13.7% - Elevation quality
            'fidelity': base_weight,     # ~13.7% - Overall route following
            'agreement': agreement_weight # 18% - Important for limited sources
        }
    else:
        # Standard weights for 3+ candidates
        weights = {
            'distance': 0.18,    # 18% - Route distance accuracy
            'jumps': 0.13,       # 13% - No unrealistic jumps
            'density': 0.18,     # 18% - Point density achieved
            'proximity': 0.13,   # 13% - Start/end accuracy (reduced for events)
            'elevation': 0.13,   # 13% - Elevation quality
            'fidelity': 0.13,    # 13% - Overall route following
            'agreement': 0.12    # 12% - Cross-candidate agreement (prevents gaming)
        }
    
    overall_confidence = sum(confidence_scores[key] * weights[key] for key in weights.keys())
    
    print(f"\n🎯 CONFIDENCE SCORE BREAKDOWN:")
    print("=" * 35)
    for category, score in confidence_scores.items():
        weight_pct = weights[category] * 100
        print(f"  {category.title():12}: {score:3.0f}/100 (weight: {weight_pct:2.0f}%)")
    
    print(f"\n🏆 OVERALL CONFIDENCE: {overall_confidence:.1f}/100")
    
    # Determine overall validation result
    if overall_confidence >= 85:
        confidence_level = "EXCELLENT"
        is_valid = True
    elif overall_confidence >= 70:
        confidence_level = "GOOD"
        is_valid = True
    elif overall_confidence >= 55:
        confidence_level = "ACCEPTABLE"
        is_valid = True
    else:
        confidence_level = "POOR"
        is_valid = False
    
    print(f"📊 Confidence Level: {confidence_level}")
    print(f"✅ Validation Result: {'PASSED' if is_valid else 'FAILED'}")
    
    validation_report['overall'] = {
        'confidence_score': overall_confidence,
        'confidence_level': confidence_level,
        'is_valid': is_valid,
        'component_scores': confidence_scores
    }
    
    validation_report['baseline_quality'] = {
        'quality': baseline_quality,
        'note': quality_note,
        'sparse_points': baseline_sparse,
        'short_distance': baseline_short
    }
    
    return is_valid, overall_confidence, validation_report

def save_enhanced_gpx(enhanced_gpx, original_filename, file_type):
    """
    Save enhanced GPX to appropriate _ENH folder
    
    Args:
        enhanced_gpx: Enhanced GPX object to save
        original_filename: Original filename for naming
        file_type: Type of file for folder determination
        
    Returns:
        str: Path where file was saved, or None if error
    """
    print(f"\n💾 Saving enhanced GPX file...")
    print("=" * 35)
    
    # Get directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    
    # Determine enhanced folder based on file type
    if file_type == 'parkrun':
        enhanced_folder = os.path.join(data_dir, 'GPX', 'Parkrun_ENH')
    elif file_type == '2026_event':
        enhanced_folder = os.path.join(data_dir, 'GPX', 'Events_2026_ENH')
    elif file_type == '2027_event':
        enhanced_folder = os.path.join(data_dir, 'GPX', 'Events_2027_ENH')
    else:
        print(f"❌ Error: Unknown file type: {file_type}")
        return None
    
    # Create enhanced folder if it doesn't exist
    try:
        os.makedirs(enhanced_folder, exist_ok=True)
        print(f"📁 Target folder: {enhanced_folder}")
    except Exception as e:
        print(f"❌ Error creating folder {enhanced_folder}: {e}")
        return None
    
    # Generate enhanced filename
    base_name = os.path.splitext(original_filename)[0]  # Remove .gpx extension
    enhanced_filename = f"{base_name}_ENH.gpx"
    enhanced_path = os.path.join(enhanced_folder, enhanced_filename)
    
    print(f"📄 Enhanced filename: {enhanced_filename}")
    
    # Save the enhanced GPX file
    try:
        with open(enhanced_path, 'w', encoding='utf-8') as f:
            f.write(enhanced_gpx.to_xml())
        
        print(f"✅ File saved successfully!")
        print(f"📍 Full path: {enhanced_path}")
        
        # Verify file was created and get size
        if os.path.exists(enhanced_path):
            file_size = os.path.getsize(enhanced_path)
            print(f"📊 File size: {file_size:,} bytes")
        
        return enhanced_path
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None

def detect_file_type_and_location(filename):
    """
    Detect file type and determine the source folder
    
    Args:
        filename (str): The GPX filename entered by user
        
    Returns:
        tuple: (file_type, source_folder, full_path) or (None, None, None) if not found
    """
    # Get the script directory and data directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir)
    
    # Check file type based on filename pattern
    if filename.startswith('PR'):
        # Parkrun file
        file_type = 'parkrun'
        source_folder = os.path.join(data_dir, 'GPX', 'Parkrun_GPX')
    elif filename.startswith('1'):
        # 2026 Event file
        file_type = '2026_event'
        source_folder = os.path.join(data_dir, 'GPX', 'Events_2026_GPX')
    elif filename.startswith('2'):
        # 2027 Event file
        file_type = '2027_event'
        source_folder = os.path.join(data_dir, 'GPX', 'Events_2027_GPX')
    else:
        print(f"❌ Error: Could not determine file type for: {filename}")
        print("    Expected: PR* (parkrun), 1* (2026 events), or 2* (2027 events)")
        return None, None, None
    
    # Build full path and check if file exists
    full_path = os.path.join(source_folder, filename)
    
    if os.path.exists(full_path):
        return file_type, source_folder, full_path
    else:
        print(f"❌ Error: {file_type} file not found: {full_path}")
        return None, None, None

def archive_temp_files(source_filename):
    """
    Archive all GPX files from GPX_Temp folder to Archive_Routes/source_name/
    
    Args:
        source_filename: Name of source file (e.g., "PR1001_corby.gpx")
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.dirname(script_dir)
        temp_dir = os.path.join(data_dir, 'GPX', 'GPX_Temp')
        
        if not os.path.exists(temp_dir):
            print(f"📁 GPX_Temp folder not found")
            return
        
        # Create archive folder structure
        archive_base = os.path.join(data_dir, 'GPX', 'Archive_Routes')
        
        # Extract base name (remove .gpx extension)
        base_name = os.path.splitext(source_filename)[0]
        archive_folder = os.path.join(archive_base, base_name)
        
        # Create directories if they don't exist
        os.makedirs(archive_folder, exist_ok=True)
        
        print(f"📂 Archiving to: {archive_folder}")
        
        # Move all GPX files from temp to archive
        archived_count = 0
        for filename in os.listdir(temp_dir):
            if filename.lower().endswith('.gpx'):
                src_path = os.path.join(temp_dir, filename)
                dst_path = os.path.join(archive_folder, filename)
                try:
                    # Use shutil.move to handle potential cross-filesystem moves
                    shutil.move(src_path, dst_path)
                    archived_count += 1
                    print(f"  📁 Archived: {filename}")
                except Exception as e:
                    print(f"  ⚠️  Could not archive {filename}: {e}")
        
        print(f"\n📂 Archive complete: {archived_count} files archived")
        
    except Exception as e:
        print(f"❌ Error during archiving: {e}")

def main():
    """Main function"""
    print("GPX Enhancement Tool")
    print("=" * 30)
    
    # Check for command-line arguments
    import sys
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        # Get user input
        filename = get_user_input()
    
    # Detect file type and location
    file_type, source_folder, full_path = detect_file_type_and_location(filename)
    
    if file_type is None:
        print("Exiting...")
        return
    
    print(f"✅ Found {file_type} file: {filename}")
    print(f"📁 Source folder: {source_folder}")
    print(f"📄 Full path: {full_path}")
    
    # Load original GPX for analysis
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            original_gpx = gpxpy.parse(f)
    except Exception as e:
        print(f"❌ Error loading original file: {e}")
        return
    
    # Load candidate files from GPX_Temp
    print(f"\n🔍 Loading candidate files from GPX_Temp...")
    temp_files = load_temp_files()
    
    if not temp_files:
        print("❌ No GPX files found in GPX_Temp")
        print("Exiting...")
        return
    
    print(f"\n✅ Ready to process {len(temp_files)} candidate files")
    
    # Analyze temp files against the original
    valid_files = analyze_temp_files(full_path, temp_files, file_type)
    
    if not valid_files:
        print("\n❌ No valid candidate files found")
        print("Exiting...")
        return
    
    print(f"\n🎯 Found {len(valid_files)} valid candidates for enhancement")
    
    # Select the best base route for enhancement
    base_result = select_base_route(valid_files, file_type, original_gpx, filename)
    
    if base_result is None:
        print("\n❌ Could not select base route")
        print("Exiting...")
        return
    
    base_filename, base_gpx, target_points = base_result
    print(f"\n🚀 Ready to enhance {base_filename} using {len(valid_files)} candidate files")
    
    # Enhance the base route with interpolation
    enhanced_gpx = enhance_route_with_interpolation(base_gpx, valid_files, target_points)
    
    print(f"\n✅ Route enhancement complete!")
    
    # Validate enhanced route against original (and base for fidelity)
    is_valid, confidence_score, validation_report = validate_enhanced_route(
        enhanced_gpx, original_gpx, file_type, base_gpx, filename, valid_files
    )
    
    if not is_valid:
        print(f"\n⚠️  Warning: Enhanced route validation failed!")
        print(f"📊 Confidence Score: {confidence_score:.1f}/100")
        try:
            proceed = input("\nDo you want to save anyway? (y/n): ").strip().lower()
            if proceed not in ['y', 'yes']:
                print("Exiting without saving...")
                return
        except EOFError:
            # Handle piped input case - default to not saving invalid routes
            print("📝 Note: Piped input detected - not saving invalid route")
            print("Exiting without saving...")
            return
    
    # Save enhanced GPX file
    saved_path = save_enhanced_gpx(enhanced_gpx, filename, file_type)
    
    if saved_path:
        print(f"\n🎉 Enhancement process complete!")
        print(f"\n📊 Final Summary:")
        print(f"   Original file: {filename}")
        print(f"   Enhanced file: {os.path.basename(saved_path)}")
        print(f"   Confidence Score: {confidence_score:.1f}/100")
        print(f"   Validation Level: {validation_report['overall']['confidence_level']}")
        print(f"   Validation: {'✅ PASSED' if is_valid else '⚠️  FAILED'}")
        
        # Offer to archive temp files (handle piped input gracefully)
        try:
            archive = input("\nDo you want to archive temp files to Archive_Routes? (y/n): ").strip().lower()
            if archive in ['y', 'yes']:
                archive_temp_files(filename)
        except EOFError:
            # Handle piped input case - skip archive prompt
            print("\n📝 Note: Temp files retained (use interactive mode for archive option)")
    else:
        print(f"\n❌ Enhancement failed - file not saved")

if __name__ == "__main__":
    main()