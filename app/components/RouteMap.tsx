'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import map components to avoid SSR issues
const MapContainer = dynamic(() => import('react-leaflet').then((mod) => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then((mod) => mod.TileLayer), { ssr: false });
const Polyline = dynamic(() => import('react-leaflet').then((mod) => mod.Polyline), { ssr: false });

interface RouteMapProps {
  selectedRoute: string;
  routeType: 'parkrun' | 'events_2026';
}

interface GPXPoint {
  lat: number;
  lon: number;
  ele?: number;
}

interface RouteBounds {
  center: [number, number];
  zoom: number;
  bounds: [[number, number], [number, number]];
}

export default function RouteMap({ selectedRoute, routeType }: RouteMapProps) {
  const [routePoints, setRoutePoints] = useState<GPXPoint[]>([]);
  const [routeBounds, setRouteBounds] = useState<RouteBounds | null>(null);
  const [loading, setLoading] = useState(false);
  const [mapKey, setMapKey] = useState(0); // Force map re-render

  useEffect(() => {
    if (!selectedRoute) {
      setRoutePoints([]);
      return;
    }

    const loadGPXRoute = async () => {
      setLoading(true);
      try {
        // First check if route exists in current route type
        const dataFilename = routeType === 'parkrun' ? 'Parkruns.json' : 'Events_2026.json';
        const routeResponse = await fetch(`/data/${dataFilename}`);
        const routesData = await routeResponse.json();
        const routeData = routesData.find((route: any) => String(route.event_id) === selectedRoute);
        
        if (!routeData) {
          console.log('Route not found in current route type, skipping GPX load');
          setRoutePoints([]);
          setLoading(false);
          return;
        }

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
        
        if (!response.ok) {
          console.error('GPX file not found:', filename);
          setRoutePoints([]);
          return;
        }
        
        const gpxText = await response.text();
        
        // Parse GPX using DOMParser
        const parser = new DOMParser();
        const gpxDoc = parser.parseFromString(gpxText, 'text/xml');
        const trackPoints = gpxDoc.querySelectorAll('trkpt');
        
        const points: GPXPoint[] = Array.from(trackPoints).map(point => ({
          lat: parseFloat(point.getAttribute('lat') || '0'),
          lon: parseFloat(point.getAttribute('lon') || '0'),
          ele: parseFloat(point.querySelector('ele')?.textContent || '0')
        }));
        
        setRoutePoints(points);
        
        // Calculate optimal bounds and zoom
        if (points.length > 0) {
          const lats = points.map(p => p.lat);
          const lons = points.map(p => p.lon);
          const minLat = Math.min(...lats);
          const maxLat = Math.max(...lats);
          const minLon = Math.min(...lons);
          const maxLon = Math.max(...lons);
          
          // Calculate center
          const centerLat = (minLat + maxLat) / 2;
          const centerLon = (minLon + maxLon) / 2;
          
          // Calculate appropriate zoom level based on bounds
          const latDiff = maxLat - minLat;
          const lonDiff = maxLon - minLon;
          const maxDiff = Math.max(latDiff, lonDiff);
          
          // Determine zoom level (higher zoom for smaller areas)
          let zoom = 16;
          if (maxDiff > 0.1) zoom = 11;
          else if (maxDiff > 0.05) zoom = 12;
          else if (maxDiff > 0.02) zoom = 13;
          else if (maxDiff > 0.01) zoom = 14;
          else if (maxDiff > 0.005) zoom = 15;
          
          setRouteBounds({
            center: [centerLat, centerLon],
            zoom: zoom,
            bounds: [[minLat, minLon], [maxLat, maxLon]]
          });
        }
        
        // Force map re-render by changing key
        setMapKey(prev => prev + 1);
        
      } catch (error) {
        console.error('Error loading GPX route:', error);
        setRoutePoints([]);
      } finally {
        setLoading(false);
      }
    };

    loadGPXRoute();
  }, [selectedRoute, routeType]);

  // Create polyline coordinates for Leaflet
  const polylinePositions: [number, number][] = routePoints.map(point => [point.lat, point.lon]);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Route Map
      </h3>
      <div className="w-full h-64 rounded overflow-hidden">
        {selectedRoute && routePoints.length > 0 && routeBounds ? (
          <MapContainer 
            key={mapKey} // Force complete re-render when route changes
            center={routeBounds.center} 
            zoom={routeBounds.zoom} 
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Polyline 
              positions={polylinePositions} 
              color="#3b82f6" 
              weight={4}
              opacity={0.8}
            />
          </MapContainer>
        ) : (
          <div className="w-full h-full bg-gray-100 dark:bg-gray-700 rounded border-2 border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center">
            {loading ? (
              <p className="text-gray-500 dark:text-gray-400">🗺️ Loading route...</p>
            ) : selectedRoute ? (
              <p className="text-gray-500 dark:text-gray-400">❌ Route not found</p>
            ) : (
              <p className="text-gray-500 dark:text-gray-400">Select a route to view map</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}