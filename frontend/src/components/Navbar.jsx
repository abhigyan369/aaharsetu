import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sprout, MessageSquare, Menu, X, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ConnectionsModal } from './Connections/ConnectionsModal';
import { connectionsApi } from '../services/api';
import './Navbar.css';

export const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isConnectionsOpen, setIsConnectionsOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const handleLogout = () => {
    setIsMobileMenuOpen(false);
    logout();
    navigate('/');
  };

  const closeMenu = () => {
    setIsMobileMenuOpen(false);
  };

  const fetchPendingConnections = async () => {
    if (!user) return;
    try {
      const conns = await connectionsApi.getConnections();
      const pending = conns.filter(
        (c) => c.status === 'pending' && c.addressee_id === user.id
      );
      setPendingCount(pending.length);
    } catch (e) {
      console.error('Failed to fetch connections badge:', e);
    }
  };

  useEffect(() => {
    if (user) {
      fetchPendingConnections();
      const interval = setInterval(fetchPendingConnections, 15000);
      return () => clearInterval(interval);
    }
  }, [user]);

  const handleOpenPrivateChat = (channelId, peerName) => {
    const chatTrigger = document.querySelector('.chat-trigger-btn');
    if (chatTrigger) {
      chatTrigger.click();
      // Dispatch custom event to select private channel
      window.dispatchEvent(
        new CustomEvent('open_private_chat', { detail: { channelId, peerName } })
      );
    }
  };

  return (
    <>
      <header className="navbar-header bg-white/95 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" onClick={closeMenu} className="flex items-center gap-2.5 text-xl font-bold text-[#2D6A4F] hover:text-[#1B4332] transition-colors">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-[#2D6A4F]">
              <Sprout className="w-5 h-5 text-[#2D6A4F]" />
            </div>
            <span className="tracking-tight font-bold text-gray-900">Aahar<span className="text-[#2D6A4F]">Setu</span></span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-6">
            <Link to="/browse" className="text-sm font-medium text-gray-700 hover:text-[#2D6A4F] transition-colors">
              Browse Food
            </Link>

            {user ? (
              <>
                {user.role === 'donor' && (
                  <Link to="/donor/dashboard" className="text-sm font-medium text-gray-700 hover:text-[#2D6A4F] transition-colors">
                    Donor Dashboard
                  </Link>
                )}
                {user.role === 'admin' && (
                  <Link to="/admin/dashboard" className="text-sm font-medium text-gray-700 hover:text-[#2D6A4F] transition-colors">
                    Admin Dashboard
                  </Link>
                )}

                {/* Connections Trigger */}
                <button
                  type="button"
                  className="text-sm font-medium text-gray-700 hover:text-[#2D6A4F] flex items-center gap-1.5 transition-colors cursor-pointer bg-transparent border-0 p-0 relative"
                  onClick={() => setIsConnectionsOpen(true)}
                >
                  <Users className="w-4 h-4 text-[#2D6A4F]" />
                  <span>Connections</span>
                  {pendingCount > 0 && (
                    <span className="bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-0.5">
                      {pendingCount}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  className="text-sm font-medium text-gray-700 hover:text-[#2D6A4F] flex items-center gap-1.5 transition-colors cursor-pointer bg-transparent border-0 p-0"
                  onClick={() => {
                    const chatTrigger = document.querySelector('.chat-trigger-btn');
                    if (chatTrigger) chatTrigger.click();
                  }}
                >
                  <MessageSquare className="w-4 h-4 text-[#2D6A4F]" />
                  <span>Live Chat</span>
                </button>

                <div className="flex items-center gap-3 pl-2 border-l border-gray-200">
                  <span className="text-xs font-semibold px-3 py-1 rounded-full bg-emerald-50 text-[#1B4332] border border-emerald-100">
                    {user.name} ({user.role})
                  </span>
                  <button onClick={handleLogout} className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-red-600 border border-gray-200 rounded-md hover:bg-gray-50 transition-all">
                    Logout
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-3">
                <Link
                  to="/login"
                  className="px-4 py-2 text-sm font-medium text-[#2D6A4F] border border-[#2D6A4F] rounded-lg hover:bg-[#2D6A4F] hover:text-white transition-all duration-200 shadow-xs"
                >
                  Log In
                </Link>
                <Link
                  to="/signup"
                  className="px-4 py-2 text-sm font-semibold text-white bg-[#2D6A4F] hover:bg-[#1B4332] rounded-lg transition-all duration-200 shadow-sm hover:shadow-md"
                >
                  Sign Up
                </Link>
              </div>
            )}
          </nav>

          {/* Mobile Hamburger Toggle Button */}
          <button
            type="button"
            className="md:hidden p-2 rounded-lg text-gray-700 hover:bg-gray-100 focus:outline-none"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            aria-label="Toggle Navigation Menu"
          >
            {isMobileMenuOpen ? <X className="w-6 h-6 text-gray-800" /> : <Menu className="w-6 h-6 text-gray-800" />}
          </button>
        </div>

        {/* Mobile Collapsible Navigation Drawer */}
        {isMobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 bg-white px-4 pt-3 pb-6 space-y-4 shadow-lg animate-in slide-in-from-top duration-200">
            <Link
              to="/browse"
              onClick={closeMenu}
              className="block px-3 py-2 text-base font-medium text-gray-700 hover:bg-emerald-50 hover:text-[#2D6A4F] rounded-md transition-colors"
            >
              Browse Food
            </Link>

            {user ? (
              <>
                {user.role === 'donor' && (
                  <Link
                    to="/donor/dashboard"
                    onClick={closeMenu}
                    className="block px-3 py-2 text-base font-medium text-gray-700 hover:bg-emerald-50 hover:text-[#2D6A4F] rounded-md transition-colors"
                  >
                    Donor Dashboard
                  </Link>
                )}
                {user.role === 'admin' && (
                  <Link
                    to="/admin/dashboard"
                    onClick={closeMenu}
                    className="block px-3 py-2 text-base font-medium text-gray-700 hover:bg-emerald-50 hover:text-[#2D6A4F] rounded-md transition-colors"
                  >
                    Admin Dashboard
                  </Link>
                )}

                <button
                  type="button"
                  className="w-full text-left px-3 py-2 text-base font-medium text-gray-700 hover:bg-emerald-50 hover:text-[#2D6A4F] rounded-md transition-colors flex items-center gap-2"
                  onClick={() => {
                    closeMenu();
                    setIsConnectionsOpen(true);
                  }}
                >
                  <Users className="w-5 h-5 text-[#2D6A4F]" />
                  <span>Connections</span>
                  {pendingCount > 0 && (
                    <span className="bg-amber-500 text-white text-xs font-bold px-2 py-0.5 rounded-full ml-auto">
                      {pendingCount}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  className="w-full text-left px-3 py-2 text-base font-medium text-gray-700 hover:bg-emerald-50 hover:text-[#2D6A4F] rounded-md transition-colors flex items-center gap-2"
                  onClick={() => {
                    closeMenu();
                    const chatTrigger = document.querySelector('.chat-trigger-btn');
                    if (chatTrigger) chatTrigger.click();
                  }}
                >
                  <MessageSquare className="w-5 h-5 text-[#2D6A4F]" />
                  <span>Live Chat</span>
                </button>

                <div className="pt-3 border-t border-gray-200 space-y-3">
                  <div className="px-3 text-sm font-semibold text-[#1B4332]">
                    Signed in as: <span className="bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100 text-xs">{user.name} ({user.role})</span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full px-3 py-2 text-left text-base font-medium text-red-600 hover:bg-red-50 rounded-md transition-colors"
                  >
                    Logout
                  </button>
                </div>
              </>
            ) : (
              <div className="pt-3 border-t border-gray-200 flex flex-col gap-2">
                <Link
                  to="/login"
                  onClick={closeMenu}
                  className="w-full text-center px-4 py-2.5 text-base font-medium text-[#2D6A4F] border border-[#2D6A4F] rounded-lg hover:bg-emerald-50 transition-colors"
                >
                  Log In
                </Link>
                <Link
                  to="/signup"
                  onClick={closeMenu}
                  className="w-full text-center px-4 py-2.5 text-base font-semibold text-white bg-[#2D6A4F] hover:bg-[#1B4332] rounded-lg transition-colors shadow-sm"
                >
                  Sign Up
                </Link>
              </div>
            )}
          </div>
        )}
      </header>

      {/* Connections Modal */}
      <ConnectionsModal
        isOpen={isConnectionsOpen}
        onClose={() => setIsConnectionsOpen(false)}
        onOpenPrivateChat={handleOpenPrivateChat}
      />
    </>
  );
};
