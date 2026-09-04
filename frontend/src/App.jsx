import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { ProtectedRoute } from './components/ProtectedRoute';

import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { BrowsePage } from './pages/BrowsePage';
import { ListingDetailPage } from './pages/ListingDetailPage';
import { DonorDashboardPage } from './pages/DonorDashboardPage';
import { CreateListingPage } from './pages/CreateListingPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { UnifiedChatWidget } from './components/Chat/UnifiedChatWidget';

export function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="app-shell">
          <Navbar />
          <main style={{ minHeight: 'calc(100vh - 140px)' }}>
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/browse" element={<BrowsePage />} />
              <Route path="/listings/:id" element={<ListingDetailPage />} />

              {/* Donor Protected Routes */}
              <Route
                path="/donor/dashboard"
                element={
                  <ProtectedRoute requiredRole="donor">
                    <DonorDashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/listings/new"
                element={
                  <ProtectedRoute requiredRole="donor">
                    <CreateListingPage />
                  </ProtectedRoute>
                }
              />

              {/* Admin Protected Routes */}
              <Route
                path="/admin/dashboard"
                element={
                  <ProtectedRoute requiredRole="admin">
                    <AdminDashboardPage />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </main>
          <Footer />
          <UnifiedChatWidget />
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;
