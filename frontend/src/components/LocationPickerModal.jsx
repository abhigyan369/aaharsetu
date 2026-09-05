import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default Leaflet icon assets in Webpack/Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export const LocationPickerModal = ({
  isOpen,
  onClose,
  onSave,
  initialLat,
  initialLng,
  initialAddress,
  title = "Select Location on OpenStreetMap"
}) => {
  const mapRef = useRef(null);
  const leafletMap = useRef(null);
  const markerRef = useRef(null);

  // Default to New Delhi/India central if no lat/lng, or user provided coords
  const defaultLat = parseFloat(initialLat) || 28.6139;
  const defaultLng = parseFloat(initialLng) || 77.2090;

  const [lat, setLat] = useState(defaultLat);
  const [lng, setLng] = useState(defaultLng);
  const [address, setAddress] = useState(initialAddress || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [geocoding, setGeocoding] = useState(false);

  useEffect(() => {
    if (initialLat && !isNaN(parseFloat(initialLat))) setLat(parseFloat(initialLat));
    if (initialLng && !isNaN(parseFloat(initialLng))) setLng(parseFloat(initialLng));
    if (initialAddress) setAddress(initialAddress);
  }, [initialLat, initialLng, initialAddress, isOpen]);

  // Reverse geocode lat/lng to human readable address using OpenStreetMap Nominatim
  const reverseGeocode = async (latitude, longitude) => {
    try {
      setGeocoding(true);
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`
      );
      if (response.ok) {
        const data = await response.json();
        if (data && data.display_name) {
          setAddress(data.display_name);
        }
      }
    } catch (err) {
      console.warn("Reverse geocode error:", err);
    } finally {
      setGeocoding(false);
    }
  };

  // Initialize Leaflet map on modal open
  useEffect(() => {
    if (!isOpen || !mapRef.current) return;

    if (!leafletMap.current) {
      const map = L.map(mapRef.current).setView([lat, lng], 14);

      // OpenStreetMap Tile Layer
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const marker = L.marker([lat, lng], { draggable: true }).addTo(map);

      marker.on('dragend', async () => {
        const position = marker.getLatLng();
        setLat(position.lat);
        setLng(position.lng);
        await reverseGeocode(position.lat, position.lng);
      });

      map.on('click', async (e) => {
        const { lat: clickLat, lng: clickLng } = e.latlng;
        marker.setLatLng([clickLat, clickLng]);
        setLat(clickLat);
        setLng(clickLng);
        await reverseGeocode(clickLat, clickLng);
      });

      leafletMap.current = map;
      markerRef.current = marker;

      // Trigger map resize invalidate after modal opens
      setTimeout(() => {
        map.invalidateSize();
      }, 200);
    } else {
      leafletMap.current.setView([lat, lng], 14);
      if (markerRef.current) {
        markerRef.current.setLatLng([lat, lng]);
      }
      setTimeout(() => {
        leafletMap.current?.invalidateSize();
      }, 200);
    }

    return () => {
      if (!isOpen && leafletMap.current) {
        leafletMap.current.remove();
        leafletMap.current = null;
        markerRef.current = null;
      }
    };
  }, [isOpen]);

  // Handle manual address search via OpenStreetMap Nominatim
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    try {
      setIsSearching(true);
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}`
      );
      if (res.ok) {
        const results = await res.json();
        if (results && results.length > 0) {
          const first = results[0];
          const newLat = parseFloat(first.lat);
          const newLng = parseFloat(first.lon);

          setLat(newLat);
          setLng(newLng);
          setAddress(first.display_name);

          if (leafletMap.current) {
            leafletMap.current.setView([newLat, newLng], 15);
          }
          if (markerRef.current) {
            markerRef.current.setLatLng([newLat, newLng]);
          }
        } else {
          alert('No location results found. Try clicking directly on the map!');
        }
      }
    } catch (err) {
      console.error('Location search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  // Browser Geolocation API
  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const myLat = position.coords.latitude;
        const myLng = position.coords.longitude;

        setLat(myLat);
        setLng(myLng);

        if (leafletMap.current) {
          leafletMap.current.setView([myLat, myLng], 15);
        }
        if (markerRef.current) {
          markerRef.current.setLatLng([myLat, myLng]);
        }

        await reverseGeocode(myLat, myLng);
      },
      (err) => {
        console.warn('Geolocation error:', err);
        alert('Could not retrieve current location. Please pick location on the map.');
      }
    );
  };

  const handleSave = () => {
    onSave({
      latitude: parseFloat(Number(lat).toFixed(6)),
      longitude: parseFloat(Number(lng).toFixed(6)),
      address: address || `Lat: ${lat.toFixed(4)}, Lon: ${lng.toFixed(4)}`
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.6)',
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem'
    }}>
      <div className="card" style={{
        width: '100%',
        maxWidth: '750px',
        maxHeight: '90vh',
        height: 'auto',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: '0 20px 25px -5px rgba(0,0,0,0.3)'
      }}>
        {/* Header */}
        <div style={{
          padding: '1rem 1.5rem',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#f8fafc',
          flexShrink: 0
        }}>
          <h3 style={{ margin: 0, color: 'var(--color-primary)', fontSize: '1.25rem' }}>
            🗺️ {title}
          </h3>
          <button
            onClick={onClose}
            className="btn btn-outline btn-sm"
            style={{ border: 'none', fontSize: '1.2rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {/* Scrollable Modal Content */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '1.25rem 1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          {/* Search & Actions Bar */}
          <div>
            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Search address or area on OpenStreetMap..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ flex: 1 }}
              />
              <button type="submit" className="btn btn-primary" disabled={isSearching}>
                {isSearching ? 'Searching...' : '🔍 Search'}
              </button>
              <button
                type="button"
                onClick={handleUseMyLocation}
                className="btn btn-outline"
                title="Use Current GPS"
              >
                📍 My Location
              </button>
            </form>
            <div style={{ fontSize: '0.825rem', color: 'var(--color-text-muted)' }}>
              💡 <i>Click anywhere on the map or drag the marker to pinpoint exact location.</i>
            </div>
          </div>

          {/* Leaflet Map Canvas */}
          <div
            ref={mapRef}
            style={{
              height: '280px',
              minHeight: '220px',
              width: '100%',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              overflow: 'hidden'
            }}
          />

          {/* Address & Coords Display */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div>
              <label className="form-label" style={{ marginBottom: '0.25rem', fontSize: '0.85rem' }}>
                Selected Address {geocoding && <span style={{ color: '#3b82f6' }}>(updating address...)</span>}
              </label>
              <input
                type="text"
                className="form-input"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="e.g. 123 MG Road, Sector 4, Bengaluru"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label className="form-label" style={{ marginBottom: '0.25rem', fontSize: '0.8rem' }}>Latitude</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  value={lat}
                  onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
                />
              </div>
              <div>
                <label className="form-label" style={{ marginBottom: '0.25rem', fontSize: '0.8rem' }}>Longitude</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  value={lng}
                  onChange={(e) => setLng(parseFloat(e.target.value) || 0)}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Footer buttons (pinned at bottom) */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '0.75rem',
          backgroundColor: '#f8fafc',
          flexShrink: 0
        }}>
          <button onClick={onClose} className="btn btn-outline">
            Cancel
          </button>
          <button onClick={handleSave} className="btn btn-primary">
            Confirm & Save Location
          </button>
        </div>
      </div>
    </div>
  );
};
