import React from 'react';
import { Link } from 'react-router-dom';
import { Utensils, HeartHandshake, TrendingUp, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { FaqSection } from '../components/FaqSection';

export const HomePage = () => {
  const { user } = useAuth();

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-12">
      {/* Hero Card */}
      <div className="bg-[#1B4332] rounded-3xl p-6 sm:p-12 md:p-14 text-center text-white mb-8 sm:mb-16 shadow-xl relative overflow-hidden">
        {/* Subtle background decorative element */}
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-emerald-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl mx-auto">
          <h1 className="text-2xl sm:text-4xl md:text-5xl font-extrabold tracking-tight mb-4 sm:mb-5 text-white leading-tight">
            Bridging Surplus Food with Community Need
          </h1>
          <p className="text-sm sm:text-lg md:text-xl text-emerald-100/90 leading-relaxed font-normal max-w-2xl mx-auto mb-6 sm:mb-10">
            AaharSetu empowers restaurants, stores, and individuals to donate edible surplus food directly to local receivers and charities in real-time.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
            <Link
              to="/browse"
              className="w-full sm:w-auto px-6 py-3.5 bg-white text-[#1B4332] font-semibold text-base rounded-xl shadow-md hover:bg-emerald-50 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 flex items-center justify-center gap-2"
            >
              <Utensils className="w-5 h-5 text-[#1B4332]" />
              <span>Browse Available Food</span>
            </Link>
            {!user && (
              <Link
                to="/signup"
                className="w-full sm:w-auto px-6 py-3.5 bg-white/15 hover:bg-white/25 border border-white/30 text-white font-medium text-base rounded-xl backdrop-blur-sm shadow-xs hover:-translate-y-0.5 transition-all duration-200 flex items-center justify-center gap-2"
              >
                <span>Join Platform</span>
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Feature Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
        {/* Card 1: For Donors */}
        <Link
          to={user?.role === 'donor' ? '/donor/dashboard' : '/signup'}
          className="group bg-white rounded-2xl p-6 sm:p-8 border border-gray-200/80 shadow-xs hover:shadow-md hover:-translate-y-1 transition-all duration-200 flex flex-col justify-between"
        >
          <div>
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#2D6A4F] flex items-center justify-center mb-6 group-hover:bg-emerald-100 transition-colors">
              <Utensils className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-[#2D6A4F] transition-colors">
              For Donors
            </h3>
            <p className="text-gray-600 text-sm leading-relaxed mb-6">
              List excess prepared food, groceries, or bakery items in under 60 seconds with location and expiry details.
            </p>
          </div>
          <div className="flex items-center text-sm font-semibold text-[#2D6A4F]">
            <span>Go to Donor Portal</span>
            <ArrowRight className="w-4 h-4 ml-1.5 transition-transform group-hover:translate-x-1" />
          </div>
        </Link>

        {/* Card 2: For Receivers */}
        <Link
          to="/browse"
          className="group bg-white rounded-2xl p-6 sm:p-8 border border-gray-200/80 shadow-xs hover:shadow-md hover:-translate-y-1 transition-all duration-200 flex flex-col justify-between"
        >
          <div>
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#2D6A4F] flex items-center justify-center mb-6 group-hover:bg-emerald-100 transition-colors">
              <HeartHandshake className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-[#2D6A4F] transition-colors">
              For Receivers
            </h3>
            <p className="text-gray-600 text-sm leading-relaxed mb-6">
              Discover nearby food listings, filter by food type and distance, and claim items instantly before expiry.
            </p>
          </div>
          <div className="flex items-center text-sm font-semibold text-[#2D6A4F]">
            <span>Explore Listings</span>
            <ArrowRight className="w-4 h-4 ml-1.5 transition-transform group-hover:translate-x-1" />
          </div>
        </Link>

        {/* Card 3: Community Impact */}
        <Link
          to="/admin/dashboard"
          className="group bg-white rounded-2xl p-6 sm:p-8 border border-gray-200/80 shadow-xs hover:shadow-md hover:-translate-y-1 transition-all duration-200 flex flex-col justify-between"
        >
          <div>
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#2D6A4F] flex items-center justify-center mb-6 group-hover:bg-emerald-100 transition-colors">
              <TrendingUp className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-[#2D6A4F] transition-colors">
              Community Impact
            </h3>
            <p className="text-gray-600 text-sm leading-relaxed mb-6">
              Track total redistributions, food categories saved, and active community participation metrics.
            </p>
          </div>
          <div className="flex items-center text-sm font-semibold text-[#2D6A4F]">
            <span>View Live Impact</span>
            <ArrowRight className="w-4 h-4 ml-1.5 transition-transform group-hover:translate-x-1" />
          </div>
        </Link>
      </div>

      {/* FAQ Section */}
      <FaqSection />
    </div>
  );
};

