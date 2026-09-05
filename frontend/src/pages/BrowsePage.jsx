import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listingsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { LocationPickerModal } from '../components/LocationPickerModal';
import { DonationMapView } from '../components/DonationMapView';

export const BrowsePage = () => {
  const { user, updateProfile } = useAuth();
  const navigate = useNavigate();

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [claimStatusMsg, setClaimStatusMsg] = useState({ type: '', text: '' });

  // Location state (initialized from user profile if available, or default central India)
  const [receiverLat, setReceiverLat] = useState(user?.latitude ? String(user.latitude) : '28.6139');
  const [receiverLng, setReceiverLng] = useState(user?.longitude ? String(user.longitude) : '77.2090');
  const [receiverAddress, setReceiverAddress] = useState(user?.address || 'Default Location');
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);

  // Filters
  const [foodTypeFilter, setFoodTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('available');
  const [radiusFilter, setRadiusFilter] = useState('10'); // Default 10 km radius requirement
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'map'

  // Update receiver state when user profile loads
  useEffect(() => {
    if (user?.latitude && user?.longitude) {
      setReceiverLat(String(user.latitude));
      setReceiverLng(String(user.longitude));
      if (user.address) setReceiverAddress(user.address);
    }
  }, [user]);

  const fetchListings = async () => {
    try {
      setLoading(true);
      setError('');
      const params = {};
      if (foodTypeFilter) params.food_type = foodTypeFilter;
      if (statusFilter) params.status = statusFilter;

      // Pass proximity params for Haversine calculation & nearest donor sorting
      if (receiverLat && receiverLng) {
        params.lat = receiverLat;
        params.lon = receiverLng;
        if (radiusFilter !== 'all') {
          params.max_distance_km = radiusFilter;
        }
      }

      const data = await listingsApi.getAll(params);
      let items = Array.isArray(data) ? data : (data.items || []);
      setListings(items);
    } catch (err) {
      setError(err.message || 'Failed to fetch listings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchListings();
  }, [foodTypeFilter, statusFilter, radiusFilter, receiverLat, receiverLng]);

  const handleSaveLocation = async (loc) => {
    if (loc.latitude) setReceiverLat(String(loc.latitude));
    if (loc.longitude) setReceiverLng(String(loc.longitude));
    if (loc.address) setReceiverAddress(loc.address);

    // Persist to DB if user is logged in
    if (user) {
      try {
        await updateProfile({
          latitude: loc.latitude,
          longitude: loc.longitude,
          address: loc.address
        });
      } catch (err) {
        console.warn("Could not persist user location profile:", err);
      }
    }
  };

  const handleUseGPS = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const latVal = String(pos.coords.latitude);
        const lngVal = String(pos.coords.longitude);
        setReceiverLat(latVal);
        setReceiverLng(lngVal);

        let resolvedAddr = `GPS (${parseFloat(latVal).toFixed(4)}, ${parseFloat(lngVal).toFixed(4)})`;
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latVal}&lon=${lngVal}`);
          if (res.ok) {
            const data = await res.json();
            if (data?.display_name) resolvedAddr = data.display_name;
          }
        } catch (e) {
          // ignore error
        }

        setReceiverAddress(resolvedAddr);

        if (user) {
          try {
            await updateProfile({
              latitude: parseFloat(latVal),
              longitude: parseFloat(lngVal),
              address: resolvedAddr
            });
          } catch (err) {
            console.warn(err);
          }
        }
      },
      (err) => {
        alert('Could not retrieve current location. Please select location on OpenStreetMap.');
      }
    );
  };

  const handleClaim = async (listingId) => {
    if (!user) {
      navigate('/login');
      return;
    }

    if (user.role === 'donor') {
      setClaimStatusMsg({
        type: 'error',
        text: 'Only Receiver accounts can claim food listings. Please sign in as a receiver.'
      });
      return;
    }

    try {
      setClaimStatusMsg({ type: '', text: '' });
      await listingsApi.claim(listingId);
      setClaimStatusMsg({
        type: 'success',
        text: `Success! You have claimed listing #${listingId}. Please check details for pickup instructions.`
      });
      fetchListings();
    } catch (err) {
      setClaimStatusMsg({
        type: 'error',
        text: err.message || 'Failed to claim listing. It may already be claimed.'
      });
    }
  };

  return (
    <div className="container main-content">
      <div style={{ marginBottom: '1.5rem', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
        <div>
          <h1 style={{ color: 'var(--color-primary)', marginBottom: '0.5rem' }}>Browse Available Food</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>
            Discover surplus food near you, calculated via OpenStreetMap & Haversine distance formula.
          </p>
        </div>

        {/* View Toggle */}
        <div style={{ display: 'flex', gap: '0.5rem', backgroundColor: '#f1f5f9', padding: '0.25rem', borderRadius: '8px' }}>
          <button
            onClick={() => setViewMode('grid')}
            className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-outline'}`}
            style={{ border: 'none' }}
          >
            📋 Grid View
          </button>
          <button
            onClick={() => setViewMode('map')}
            className={`btn btn-sm ${viewMode === 'map' ? 'btn-primary' : 'btn-outline'}`}
            style={{ border: 'none' }}
          >
            🗺️ OpenStreetMap View
          </button>
        </div>
      </div>

      {claimStatusMsg.text && (
        <div className={`alert alert-${claimStatusMsg.type}`}>
          {claimStatusMsg.text}
        </div>
      )}

      {/* Receiver Location Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem', backgroundColor: '#f8fafc', borderLeft: '4px solid var(--color-primary)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
          <div style={{ flex: 1, minWidth: '250px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-primary)', letterSpacing: '0.05em' }}>
              📍 Receiver Location (Distance Center)
            </div>
            <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a', overflowWrap: 'break-word' }}>
              {receiverAddress}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              Lat: {parseFloat(receiverLat).toFixed(4)}, Lon: {parseFloat(receiverLng).toFixed(4)}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button onClick={() => setIsLocationModalOpen(true)} className="btn btn-outline btn-sm">
              🗺️ Select on OpenStreetMap
            </button>
            <button onClick={handleUseGPS} className="btn btn-outline btn-sm">
              📍 Use Current GPS
            </button>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '2rem', padding: '1.25rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'center' }}>
          <div>
            <label className="form-label" htmlFor="foodTypeFilter">Food Category</label>
            <select
              id="foodTypeFilter"
              className="form-select"
              value={foodTypeFilter}
              onChange={(e) => setFoodTypeFilter(e.target.value)}
            >
              <option value="">All Categories</option>
              <option value="cooked">Cooked Food</option>
              <option value="packaged">Packaged Food</option>
              <option value="produce">Fresh Produce</option>
              <option value="bakery">Bakery Items</option>
              <option value="dairy">Dairy Products</option>
              <option value="beverage">Beverages</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="statusFilter">Status</label>
            <select
              id="statusFilter"
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="available">Available Now</option>
              <option value="claimed">Claimed</option>
              <option value="">All Listings</option>
            </select>
          </div>

          <div>
            <label className="form-label" htmlFor="radiusFilter">Distance Radius</label>
            <select
              id="radiusFilter"
              className="form-select"
              value={radiusFilter}
              onChange={(e) => setRadiusFilter(e.target.value)}
            >
              <option value="2">Within 2 km</option>
              <option value="5">Within 5 km</option>
              <option value="10">Within 10 km (Default)</option>
              <option value="25">Within 25 km</option>
              <option value="50">Within 50 km</option>
              <option value="all">All Distances</option>
            </select>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Content Rendering: Map or Grid View */}
      {loading ? (
        <p style={{ textAlign: 'center', padding: '3rem 0' }}>Calculating distances and loading available food listings...</p>
      ) : listings.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--color-text-muted)' }}>
          <h3>No listings found within {radiusFilter === 'all' ? 'any distance' : `${radiusFilter} km`}.</h3>
          <p style={{ marginTop: '0.5rem' }}>Try expanding your distance radius or changing food filters!</p>
        </div>
      ) : viewMode === 'map' ? (
        <DonationMapView
          listings={listings}
          receiverLat={receiverLat}
          receiverLng={receiverLng}
          receiverAddress={receiverAddress}
          height="520px"
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
          {listings.map((item) => (
            <div key={item.id} className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                <span className={`badge badge-${item.status}`}>{item.status}</span>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                  {item.food_type}
                </span>
              </div>

              <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>
                <Link to={`/listings/${item.id}`}>{item.title}</Link>
              </h3>

              {/* Haversine distance badge */}
              {item.distance_km !== undefined && item.distance_km !== null && (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  backgroundColor: '#dcfce7',
                  color: '#15803d',
                  padding: '0.25rem 0.6rem',
                  borderRadius: '9999px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  marginBottom: '0.75rem',
                  width: 'fit-content'
                }}>
                  📍 {item.distance_km} km away
                </div>
              )}

              <p style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginBottom: '1rem', flex: 1 }}>
                {item.description || 'No description provided.'}
              </p>

              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem', marginBottom: '1rem' }}>
                <div><strong>Quantity:</strong> {item.quantity} {item.quantity_unit || ''}</div>
                <div style={{ overflowWrap: 'break-word' }}><strong>Location:</strong> {item.address || 'Address not specified'}</div>
                {item.expiry_time && (
                  <div><strong>Expires:</strong> {new Date(item.expiry_time).toLocaleString()}</div>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <Link to={`/listings/${item.id}`} className="btn btn-outline" style={{ flex: 1, minWidth: '120px' }}>
                  View Details
                </Link>
                {item.status === 'available' && (
                  <button
                    onClick={() => handleClaim(item.id)}
                    className="btn btn-primary"
                    style={{ flex: 1, minWidth: '120px' }}
                  >
                    Claim Food
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Location Picker Modal for Receivers */}
      <LocationPickerModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        onSave={handleSaveLocation}
        initialLat={receiverLat}
        initialLng={receiverLng}
        initialAddress={receiverAddress}
        title="Set Receiver Location on OpenStreetMap"
      />
    </div>
  );
};
