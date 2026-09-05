import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { listingsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { LocationPickerModal } from '../components/LocationPickerModal';

export const CreateListingPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [foodType, setFoodType] = useState('cooked');
  const [quantity, setQuantity] = useState('');
  const [quantityUnit, setQuantityUnit] = useState('portions');
  const [address, setAddress] = useState(user?.address || '');
  const [expiryTime, setExpiryTime] = useState('');
  const [latitude, setLatitude] = useState(user?.latitude ? String(user.latitude) : '28.6139');
  const [longitude, setLongitude] = useState(user?.longitude ? String(user.longitude) : '77.2090');
  const [imageFile, setImageFile] = useState(null);

  const [isMapModalOpen, setIsMapModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) {
      if (user.address) setAddress(user.address);
      if (user.latitude) setLatitude(String(user.latitude));
      if (user.longitude) setLongitude(String(user.longitude));
    }
  }, [user]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setImageFile(e.target.files[0]);
    }
  };

  const handleLocationSaved = (loc) => {
    if (loc.latitude) setLatitude(String(loc.latitude));
    if (loc.longitude) setLongitude(String(loc.longitude));
    if (loc.address) setAddress(loc.address);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      let finalLat = latitude;
      let finalLng = longitude;

      // Auto-geocode address if lat/lon are missing or default
      if (address && (finalLat === '28.6139' || finalLat === '37.7749' || !finalLat)) {
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`);
          if (res.ok) {
            const data = await res.json();
            if (data && data.length > 0) {
              finalLat = String(data[0].lat);
              finalLng = String(data[0].lon);
            }
          }
        } catch (err) {
          console.warn("Auto-geocode failed:", err);
        }
      }

      const formData = new FormData();
      formData.append('title', title);
      formData.append('description', description);
      formData.append('food_type', foodType);
      formData.append('quantity', quantity);
      formData.append('quantity_unit', quantityUnit);
      formData.append('address', address);
      formData.append('latitude', finalLat);
      formData.append('longitude', finalLng);

      if (expiryTime) {
        formData.append('expiry_time', new Date(expiryTime).toISOString());
      }

      if (imageFile) {
        formData.append('image', imageFile);
      }

      await listingsApi.create(formData);
      navigate('/donor/dashboard');
    } catch (err) {
      setError(err.message || 'Failed to create listing. Please check form fields.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container main-content" style={{ maxWidth: '650px' }}>
      <div className="card" style={{ padding: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ color: 'var(--color-primary)' }}>Post Surplus Food Listing</h2>
          <Link to="/donor/dashboard" className="btn btn-outline btn-sm">Cancel</Link>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="title">Listing Title *</label>
            <input
              id="title"
              type="text"
              className="form-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              placeholder="e.g. 15 Trays of Fresh Rice & Curry"
            />
          </div>

          <div className="form-group grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="form-label" htmlFor="foodType">Food Category *</label>
              <select
                id="foodType"
                className="form-select"
                value={foodType}
                onChange={(e) => setFoodType(e.target.value)}
              >
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
              <label className="form-label" htmlFor="quantity">Quantity *</label>
              <input
                id="quantity"
                type="number"
                step="any"
                min="0.1"
                className="form-input"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
                placeholder="e.g. 20"
              />
            </div>

            <div>
              <label className="form-label" htmlFor="quantityUnit">Unit *</label>
              <input
                id="quantityUnit"
                type="text"
                className="form-input"
                value={quantityUnit}
                onChange={(e) => setQuantityUnit(e.target.value)}
                required
                placeholder="e.g. portions / kg"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="description">Description</label>
            <textarea
              id="description"
              className="form-textarea"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Provide details such as dietary info (veg/non-veg), packaging, or pickup instructions."
            />
          </div>

          {/* Location Section with Leaflet Map Selector */}
          <div className="form-group" style={{ backgroundColor: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <label className="form-label" style={{ margin: 0 }}>📍 Pickup Location & Coords *</label>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setIsMapModalOpen(true)}
              >
                🗺️ Select on OpenStreetMap
              </button>
            </div>

            <input
              id="address"
              type="text"
              className="form-input"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
              placeholder="Full pickup address (e.g. 123 Main St, Community Center)"
              style={{ marginBottom: '0.75rem' }}
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div>
                <span style={{ color: 'var(--color-text-muted)' }}>Lat:</span> <strong>{latitude}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)' }}>Lon:</span> <strong>{longitude}</strong>
              </div>
            </div>
          </div>

          <div className="form-group grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="form-label" htmlFor="expiryTime">Best Before / Expiry Time</label>
              <input
                id="expiryTime"
                type="datetime-local"
                className="form-input"
                value={expiryTime}
                onChange={(e) => setExpiryTime(e.target.value)}
              />
            </div>

            <div>
              <label className="form-label" htmlFor="image">Food Photo (Optional)</label>
              <input
                id="image"
                type="file"
                accept="image/*"
                className="form-input"
                onChange={handleFileChange}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ flex: 1, padding: '0.75rem' }}
              disabled={submitting}
            >
              {submitting ? 'Creating Listing...' : 'Publish Listing'}
            </button>
          </div>
        </form>
      </div>

      <LocationPickerModal
        isOpen={isMapModalOpen}
        onClose={() => setIsMapModalOpen(false)}
        onSave={handleLocationSaved}
        initialLat={latitude}
        initialLng={longitude}
        initialAddress={address}
        title="Select Exact Pickup Location"
      />
    </div>
  );
};

