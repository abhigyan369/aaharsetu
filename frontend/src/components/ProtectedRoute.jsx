/**
 * src/components/ProtectedRoute.jsx — Route Guard Component
 * ==========================================================
 * Restricts access to specific routes based on login state and optional role.
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute = ({ children, requiredRole }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '4rem 0' }}>
        <p>Loading application...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    return (
      <div className="container" style={{ padding: '3rem 0' }}>
        <div className="alert alert-error">
          <h3>Access Denied</h3>
          <p>You need {requiredRole} privileges to view this page.</p>
        </div>
      </div>
    );
  }

  return children;
};
