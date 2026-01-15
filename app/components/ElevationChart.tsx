'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface RouteData {
  event_id: number | string;
  event_name: string;
  event_slug?: string;
  [key: string]: unknown;
}

interface ElevationChartProps {
  selectedRoute: string;
  routeType: 'parkrun' | 'events_2026';  showChart?: boolean;}

interface ElevationData {
  accessibility_rating: string;
  max_elevation_m: number;
  min_elevation_m: number;
  max_gradient_pct: number;
  total_elevation_gain_m: number;
  total_elevation_loss_m: number;
  steep_5pct_longest_stretch_m: number;
  steep_8pct_longest_stretch_m: number;
  steep_5pct_distance_m: number;
  steep_8pct_distance_m: number;
  total_distance_km: number;
}

interface GPXPoint {
  lat: number;
  lon: number;
  ele?: number;
}

interface ChartDataPoint {
  distance: number;
  elevation: number;
}

export default function ElevationChart({ selectedRoute, routeType, showChart }: ElevationChartProps) {
  const [elevationData, setElevationData] = useState<ElevationData | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedRoute) return;

    const loadElevationData = async () => {
      setLoading(true);
      try {
        // First check if the route exists in the current route type
        const dataFilename = routeType === 'parkrun' ? 'Parkruns.json' : 'Events_2026.json';
        const routeResponse = await fetch(`/data/${dataFilename}`);
        const routesData = await routeResponse.json();
        const routeExists = routesData.some((route: RouteData) => String(route.event_id) === selectedRoute);
        
        if (!routeExists) {
          console.log('Route not found in current route type, skipping load');
          setElevationData(null);
          setChartData([]);
          setLoading(false);
          return;
        }

        // Load elevation analysis data
        const filename = routeType === 'parkrun' ? 'Parkrun_elevation.json' : 'Events_2026_elevation.json';
        const response = await fetch(`/data/${filename}`);
        const data = await response.json();
        
        // Find route data by matching event_id
        const routeData = data.find((route: RouteData) => String(route.event_id) === selectedRoute);
        setElevationData(routeData || null);

        // Load GPX data for chart
        await loadGPXChartData();
        
      } catch (error) {
        console.error('Error loading elevation data:', error);
        setElevationData(null);
      } finally {
        setLoading(false);
      }
    };

    const loadGPXChartData = async () => {
      try {
        // Get route slug for GPX filename
        const dataFilename = routeType === 'parkrun' ? 'Parkruns.json' : 'Events_2026.json';
        const routeResponse = await fetch(`/data/${dataFilename}`);
        const routesData = await routeResponse.json();
        const routeData = routesData.find((route: RouteData) => String(route.event_id) === selectedRoute);
        
        if (!routeData) return;

        // Generate slug from event name for events_2026
        const generateSlug = (name: string) => {
          return name.toLowerCase()
            .replace(/[^a-z0-9\s]/g, '') // Remove special characters
            .replace(/\s+/g, '') // Remove spaces
            .trim();
        };

        // Construct GPX filename
        let filename = '';
        if (routeType === 'parkrun') {
          filename = `${selectedRoute}_${routeData.event_slug}_ENH.gpx`;
        } else {
          const slug = generateSlug(routeData.event_name);
          filename = `${selectedRoute}_${slug}_runthrough_ENH.gpx`;
        }
        
        const folderPath = routeType === 'parkrun' ? 'parkrun' : 'events_2026';
        const response = await fetch(`/gpx/${folderPath}/${filename}`);
        
        if (!response.ok) return;
        
        const gpxText = await response.text();
        const parser = new DOMParser();
        const gpxDoc = parser.parseFromString(gpxText, 'text/xml');
        const trackPoints = gpxDoc.querySelectorAll('trkpt');
        
        const points: GPXPoint[] = Array.from(trackPoints).map(point => ({
          lat: parseFloat(point.getAttribute('lat') || '0'),
          lon: parseFloat(point.getAttribute('lon') || '0'),
          ele: parseFloat(point.querySelector('ele')?.textContent || '0')
        }));

        // Convert to chart data with accurate distance calculation
        const chartPoints: ChartDataPoint[] = [];
        let cumulativeDistance = 0;
        
        // Haversine formula for accurate distance calculation
        const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number) => {
          const R = 6371000; // Earth's radius in meters
          const φ1 = lat1 * Math.PI / 180;
          const φ2 = lat2 * Math.PI / 180;
          const Δφ = (lat2 - lat1) * Math.PI / 180;
          const Δλ = (lon2 - lon1) * Math.PI / 180;

          const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                    Math.cos(φ1) * Math.cos(φ2) *
                    Math.sin(Δλ/2) * Math.sin(Δλ/2);
          const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

          return R * c; // Distance in meters
        };
        
        points.forEach((point, index) => {
          if (index > 0) {
            const prevPoint = points[index - 1];
            const distance = calculateDistance(prevPoint.lat, prevPoint.lon, point.lat, point.lon);
            cumulativeDistance += distance;
          }
          
          chartPoints.push({
            distance: cumulativeDistance / 1000, // Convert to km
            elevation: point.ele || 0
          });
        });
        
        setChartData(chartPoints);
        
      } catch (error) {
        console.error('Error loading GPX chart data:', error);
        setChartData([]);
      }
    };

    loadElevationData();
  }, [selectedRoute, routeType]);

  // Show only stats if showChart is false, only chart if showChart is true
  if (showChart === false) {
    return (
      <>
        {/* Enhanced Elevation Stats Only */}
        {loading ? (
          <div className="text-center py-8">
            <p className="text-gray-500 dark:text-gray-400">Loading elevation data...</p>
          </div>
        ) : elevationData ? (
          <div className="grid grid-cols-2 gap-3">
            {/* Distance & Accessibility */}
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <p className="text-xs text-blue-600 dark:text-blue-400 font-medium">DISTANCE</p>
              <p className="text-lg font-bold text-blue-800 dark:text-blue-300">{elevationData.total_distance_km?.toFixed(1)} km</p>
              <p className="text-xs text-blue-600 dark:text-blue-400">{elevationData.accessibility_rating}</p>
            </div>
          
            {/* Elevation Range */}
            <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
              <p className="text-xs text-green-600 dark:text-green-400 font-medium">ELEVATION</p>
              <p className="text-lg font-bold text-green-800 dark:text-green-300">
                {elevationData.min_elevation_m?.toFixed(0)}m - {elevationData.max_elevation_m?.toFixed(0)}m
              </p>
              <p className="text-xs text-green-600 dark:text-green-400">
                {(elevationData.max_elevation_m - elevationData.min_elevation_m)?.toFixed(0)}m range
              </p>
            </div>
            
            {/* Max Gradient */}
            <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
              <p className="text-xs text-purple-600 dark:text-purple-400 font-medium">MAX GRADIENT</p>
              <p className="text-lg font-bold text-purple-800 dark:text-purple-300">
                {elevationData.max_gradient_pct?.toFixed(1)}%
              </p>
              <p className="text-xs text-purple-600 dark:text-purple-400">steepest section</p>
            </div>
            
            {/* Total Climbs */}
            <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3">
              <p className="text-xs text-orange-600 dark:text-orange-400 font-medium">TOTAL CLIMBS</p>
              <p className="text-lg font-bold text-orange-800 dark:text-orange-300">
                +{elevationData.total_elevation_gain_m?.toFixed(0)}m
              </p>
              <p className="text-xs text-orange-600 dark:text-orange-400">
                -{elevationData.total_elevation_loss_m?.toFixed(0)}m
              </p>
            </div>
            
            {/* 5% Climbs */}
            <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <p className="text-xs text-red-600 dark:text-red-400 font-medium">5% CLIMBS</p>
              <p className="text-lg font-bold text-red-800 dark:text-red-300">
                {elevationData.steep_5pct_distance_m?.toFixed(0)}m total
              </p>
              <p className="text-xs text-red-600 dark:text-red-400">
                Longest: {elevationData.steep_5pct_longest_stretch_m?.toFixed(0)}m
              </p>
            </div>
            
            {/* 8% Climbs */}
            <div className="bg-pink-50 dark:bg-pink-900/20 rounded-lg p-3">
              <p className="text-xs text-pink-600 dark:text-pink-400 font-medium">8% CLIMBS</p>
              <p className="text-lg font-bold text-pink-800 dark:text-pink-300">
                {elevationData.steep_8pct_distance_m?.toFixed(0)}m total
              </p>
              <p className="text-xs text-pink-600 dark:text-pink-400">
                {elevationData.steep_8pct_longest_stretch_m > 0 
                  ? `Longest: ${elevationData.steep_8pct_longest_stretch_m?.toFixed(0)}m`
                  : 'None'
                }
              </p>
            </div>
          </div>
        ) : selectedRoute ? (
          <div className="text-center py-8">
            <p className="text-gray-500 dark:text-gray-400">No elevation data found</p>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-500 dark:text-gray-400">Select a route to view elevation</p>
          </div>
        )}
      </>
    );
  }
  
  // Show only chart if showChart is true
  if (showChart === true) {
    if (!selectedRoute || chartData.length === 0) {
      return (
        <div className="text-center py-8">
          <p className="text-gray-500 dark:text-gray-400">
            {!selectedRoute ? 'Select a route to view chart' : 'No chart data available'}
          </p>
        </div>
      );
    }
    
    // Calculate fixed 50m window centered around route elevations
    const elevations = chartData.map(point => point.elevation);
    const minElev = Math.min(...elevations);
    const maxElev = Math.max(...elevations);
    const elevationRange = maxElev - minElev;
    const pad = 5; // 5m padding
    const yMin = Math.floor((minElev - pad) / 10) * 10;
    const yMax = yMin + 50; // Fixed 50m window
    
    return (
      <>
        {/* Range annotation */}
        <div className="mb-2 text-center">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Range: {elevationRange.toFixed(0)}m ({minElev.toFixed(0)}–{maxElev.toFixed(0)}m)
          </span>
        </div>
        
        <div className="h-40 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
              <XAxis 
                dataKey="distance" 
                stroke="#6B7280"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => Math.round(value).toString()}
                label={{ value: 'Distance (km)', position: 'insideBottom', offset: -5, style: { textAnchor: 'middle', fill: '#6B7280' } }}
              />
              <YAxis 
                domain={[yMin, yMax]}
                stroke="#6B7280"
                tick={{ fontSize: 12 }}
                label={{ value: 'Elevation (m)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: '#6B7280' } }}
              />
              <Tooltip 
                labelFormatter={(value) => `${Number(value).toFixed(1)} km`}
                formatter={(value) => [`${Number(value).toFixed(0)}m`, 'Elevation']}
                contentStyle={{ 
                  backgroundColor: '#1F2937', 
                  border: '1px solid #374151', 
                  borderRadius: '8px',
                  color: '#F3F4F6'
                }}
              />
              <Line 
                type="monotone" 
                dataKey="elevation" 
                stroke="#3B82F6" 
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: '#3B82F6', strokeWidth: 2, fill: '#FFFFFF' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </>
    );
  }
  
  // Default fallback (shouldn't reach here)
  return null;
}