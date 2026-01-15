
'use client';

import { useState, useEffect } from 'react';
import RouteMap from './components/RouteMap';
import ElevationChart from './components/ElevationChart';

interface Route {
  event_id: string;
  event_name: string;
  event_slug?: string;
  event_address?: string;
  event_location?: string;
  [key: string]: unknown;
}

export default function Home() {
  const [routeType, setRouteType] = useState<'parkrun' | 'events_2026'>('parkrun');
  const [routes, setRoutes] = useState<Route[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<string>('');
  const [loading, setLoading] = useState(false);

  // Load routes when route type changes
  useEffect(() => {
    const loadRoutes = async () => {
      setLoading(true);
      try {
        const filename = routeType === 'parkrun' ? 'Parkruns.json' : 'Events_2026.json';
        const response = await fetch(`/data/${filename}`);
        const data = await response.json();
        console.log(`Loaded ${filename}:`, data);
        // Filter out routes with null/undefined event_id or event_name
        const validRoutes = data.filter((route: Route) => route.event_id && route.event_name);
        setRoutes(validRoutes);
        setSelectedRoute(''); // Reset selection when switching types
      } catch (error) {
        console.error('Error loading routes:', error);
        setRoutes([]);
      } finally {
        setLoading(false);
      }
    };

    loadRoutes();
  }, [routeType]);

  return (
    <div className="min-h-screen bg-linear-to-br from-blue-50 to-green-50 dark:from-gray-900 dark:to-gray-800">
      <main className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-4">
            ♿ Route Analysis System
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 mb-8">
            Comprehensive elevation analysis and accessibility assessment for running routes
          </p>
        </div>

        {/* Route Selection Controls */}
        <div className="max-w-md mx-auto mb-8">
          {/* Toggle Switch */}
          <div className="flex items-center justify-center mb-6">
            <span className={`mr-3 font-medium ${routeType === 'parkrun' ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500'}`}>
              Parkruns
            </span>
            <button
              onClick={() => setRouteType(routeType === 'parkrun' ? 'events_2026' : 'parkrun')}
              className="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:bg-gray-700"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  routeType === 'events_2026' ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <span className={`ml-3 font-medium ${routeType === 'events_2026' ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
              2026 Events
            </span>
          </div>

          {/* Route Dropdown */}
          <div className="relative">
            <select
              value={selectedRoute}
              onChange={(e) => setSelectedRoute(e.target.value)}
              disabled={loading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-gray-800 dark:text-white dark:border-gray-600"
            >
              <option value="">
                {loading ? 'Loading routes...' : `Select a ${routeType === 'parkrun' ? 'parkrun' : '2026 event'}`}
              </option>
              {routes.map((route, index) => (
                <option key={route.event_id || `route-${index}`} value={String(route.event_id) || ''}>
                  {route.event_name || 'Unnamed Route'}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Selected Route Display */}
        {selectedRoute && (
          <div className="max-w-6xl mx-auto space-y-6">
            {/* Route Header */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Selected Route
              </h3>
              <p className="text-gray-600 dark:text-gray-300">
                Route ID: {selectedRoute}
              </p>
            </div>
            
            {/* Map and Elevation Stats Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <RouteMap selectedRoute={selectedRoute} routeType={routeType} />
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
                  📊 Elevation Profile
                </h3>
                <ElevationChart selectedRoute={selectedRoute} routeType={routeType} showChart={false} />
              </div>
            </div>
            
            {/* Full Width Elevation Chart */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
                📈 Elevation Chart
              </h3>
              <ElevationChart selectedRoute={selectedRoute} routeType={routeType} showChart={true} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
