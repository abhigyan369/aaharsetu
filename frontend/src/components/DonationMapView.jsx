import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Custom icons
const donorIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const receiverIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

export const DonationMapView = ({
  listings = [],
  receiverLat,
  receiverLng,
  receiverAddress,
  height = '480px'
}) => {
  const mapContainerRef = useRef(null);
  const leafletMapRef = useRef(null);
  const markersGroupRef = useRef(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Center map on receiver position if present, or first listing, or central India
    let centerLat = parseFloat(receiverLat);
    let centerLng = parseFloat(receiverLng);

    if (isNaN(centerLat) || isNaN(centerLng)) {
      const validListing = listings.find((item) => item.latitude && item.longitude);
      if (validListing) {
        centerLat = parseFloat(validListing.latitude);
        centerLng = parseFloat(validListing.longitude);
      } else {
        centerLat = 28.6139;
        centerLng = 77.2090;
      }
    }

    if (!leafletMapRef.current) {
      const map = L.map(mapContainerRef.current).setView([centerLat, centerLng], 12);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      markersGroupRef.current = L.featureGroup().addTo(map);
      leafletMapRef.current = map;
    } else {
      leafletMapRef.current.setView([centerLat, centerLng], 12);
    }

    // Clear previous markers
    if (markersGroupRef.current) {
      markersGroupRef.current.clearLayers();
    }

    const bounds = L.latLngBounds([]);

    // Add Receiver Location Marker if available
    if (!isNaN(parseFloat(receiverLat)) && !isNaN(parseFloat(receiverLng))) {
      const rLat = parseFloat(receiverLat);
      const rLng = parseFloat(receiverLng);
      const receiverMarker = L.marker([rLat, rLng], { icon: receiverIcon });
      receiverMarker.bindPopup(`
        <div style="font-family: sans-serif; padding: 4px;">
          <strong style="color: #2563eb; font-size: 1rem;">📍 Your Location (Receiver)</strong>
          <p style="margin: 4px 0 0; font-size: 0.85rem; color: #475569;">
            ${receiverAddress || `${rLat.toFixed(4)}, ${rLng.toFixed(4)}`}
          </p>
        </div>
      `);
      markersGroupRef.current.addLayer(receiverMarker);
      bounds.extend([rLat, rLng]);
    }

    // Add Donor Listing Markers
    listings.forEach((item) => {
      if (item.latitude && item.longitude) {
        const itemLat = parseFloat(item.latitude);
        const itemLng = parseFloat(item.longitude);

        const marker = L.marker([itemLat, itemLng], { icon: donorIcon });

        const distanceText = item.distance_km !== undefined && item.distance_km !== null
          ? `<div style="background-color: #dcfce7; color: #15803d; font-weight: 600; padding: 2px 8px; border-radius: 9999px; display: inline-block; font-size: 0.8rem; margin: 4px 0;">📍 ${item.distance_km} km away</div>`
          : '';

        const popupContent = `
          <div style="font-family: sans-serif; min-width: 180px; padding: 4px;">
            <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #16a34a; font-weight: 600;">
              ${item.food_type || 'Food Listing'}
            </div>
            <h4 style="margin: 4px 0; font-size: 1rem; color: #0f172a;">${item.title}</h4>
            <div>${distanceText}</div>
            <div style="font-size: 0.85rem; color: #475569; margin-top: 4px;">
              <strong>Quantity:</strong> ${item.quantity} ${item.quantity_unit || ''}
            </div>
            <div style="font-size: 0.8rem; color: #64748b; margin-top: 2px;">
              ${item.address || ''}
            </div>
            <div style="margin-top: 8px;">
              <a href="/listings/${item.id}" style="display: block; text-align: center; background-color: #16a34a; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 0.85rem; font-weight: 500;">
                View Details & Claim
              </a>
            </div>
          </div>
        `;

        marker.bindPopup(popupContent);
        markersGroupRef.current.addLayer(marker);
        bounds.extend([itemLat, itemLng]);
      }
    });

    // Fit bounds if markers exist
    if (markersGroupRef.current && markersGroupRef.current.getLayers().length > 0) {
      leafletMapRef.current.fitBounds(markersGroupRef.current.getBounds(), {
        padding: [40, 40],
        maxZoom: 14
      });
    }
  }, [listings, receiverLat, receiverLng, receiverAddress]);

  return (
    <div className="card" style={{ padding: '0.5rem', overflow: 'hidden' }}>
      <div
        ref={mapContainerRef}
        style={{
          height,
          width: '100%',
          borderRadius: '8px',
          zIndex: 1
        }}
      />
    </div>
  );
};
