import React, { useState } from 'react';
import { ChevronDown, Search, HelpCircle, ShieldCheck, HeartHandshake, Utensils, MessageSquare } from 'lucide-react';
import { Link } from 'react-router-dom';

const FAQ_DATA = [
  {
    id: 1,
    category: 'General',
    question: 'What is AaharSetu and how does it work?',
    answer:
      'AaharSetu is a real-time food waste redistribution platform bridging surplus food sources with community need. Restaurants, caterers, grocery stores, and individuals post edible surplus food. Receivers and local charities browse and claim active listings nearby to collect edible food before it goes to waste.',
    icon: Utensils,
  },
  {
    id: 2,
    category: 'General',
    question: 'Is AaharSetu free to use for everyone?',
    answer:
      'Yes, 100% free! AaharSetu is a non-profit community initiative created to eliminate food waste and fight hunger. Neither donors nor receivers are charged any fee to post, browse, or claim food items.',
    icon: HeartHandshake,
  },
  {
    id: 3,
    category: 'For Donors',
    question: 'How do donors post surplus food listings?',
    answer:
      'Registered donors can log in, click "Donate Food", and fill out a quick form detailing the item name, quantity, category (cooked, raw, bakery, packaged), expiry window, and pickup location. Listings go live immediately to nearby receivers.',
    icon: Utensils,
  },
  {
    id: 4,
    category: 'For Receivers',
    question: 'How do receivers claim available food?',
    answer:
      'Receivers can visit the "Browse Available Food" page to view active listings near their location. Clicking "Claim Item" reserves the food listing and enables direct communication with the donor to organize pickup.',
    icon: HeartHandshake,
  },
  {
    id: 5,
    category: 'Safety & Quality',
    question: 'How is food safety and freshness maintained?',
    answer:
      'Donors are required to disclose accurate preparation time, storage requirements, and expiry limits. Listings must meet basic hygiene standards. Furthermore, our platform automatically hides expired listings from the public feed.',
    icon: ShieldCheck,
  },
  {
    id: 6,
    category: 'For Receivers',
    question: 'Who can register as a Receiver?',
    answer:
      'Local NGOs, orphanages, old-age homes, community kitchens, shelter homes, and individuals experiencing food insecurity can register as Receivers on AaharSetu.',
    icon: HeartHandshake,
  },
  {
    id: 7,
    category: 'Safety & Quality',
    question: 'What happens when a food listing reaches its expiry time?',
    answer:
      'AaharSetu automatically tracks listing timestamps. Once the specified expiry time is reached, the listing is automatically marked as expired and removed from active search results to ensure safety.',
    icon: ShieldCheck,
  },
  {
    id: 8,
    category: 'General',
    question: 'How do donors and receivers coordinate pickup?',
    answer:
      'Once an item is claimed, an in-app real-time chat box is activated for both donor and receiver. They can exchange messages and coordinate exact pickup times and location details effortlessly.',
    icon: MessageSquare,
  },
];

const CATEGORIES = ['All', 'General', 'For Donors', 'For Receivers', 'Safety & Quality'];

export const FaqSection = () => {
  const [openId, setOpenId] = useState(1); // Default first question open
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  const toggleFaq = (id) => {
    setOpenId(openId === id ? null : id);
  };

  const filteredFaqs = FAQ_DATA.filter((faq) => {
    const matchesCategory = activeCategory === 'All' || faq.category === activeCategory;
    const matchesSearch =
      faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      faq.answer.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <section className="mt-12 sm:mt-16 bg-gradient-to-b from-emerald-50/50 to-white rounded-3xl p-6 sm:p-10 border border-emerald-100 shadow-sm">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto mb-8 sm:mb-10">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-100/80 text-[#2D6A4F] text-xs sm:text-sm font-semibold mb-3">
          <HelpCircle className="w-4 h-4" />
          <span>Got Questions? We Have Answers</span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight mb-3">
          Frequently Asked Questions
        </h2>
        <p className="text-gray-600 text-sm sm:text-base leading-relaxed">
          Learn how AaharSetu connects donors and receivers, ensures food safety, and helps eliminate food waste in our community.
        </p>
      </div>

      {/* Controls: Search & Category Filters */}
      <div className="max-w-3xl mx-auto mb-8 space-y-4">
        {/* Search Bar */}
        <div className="relative">
          <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search questions (e.g. food safety, pickup, donor)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20 focus:border-[#2D6A4F] transition-all shadow-xs"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-semibold text-gray-400 hover:text-gray-600 bg-gray-100 px-2 py-1 rounded-md"
            >
              Clear
            </button>
          )}
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-4 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all duration-200 ${
                activeCategory === cat
                  ? 'bg-[#2D6A4F] text-white shadow-xs'
                  : 'bg-white text-gray-600 hover:bg-emerald-50 hover:text-[#2D6A4F] border border-gray-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Accordion FAQ List */}
      <div className="max-w-3xl mx-auto space-y-3">
        {filteredFaqs.length > 0 ? (
          filteredFaqs.map((faq) => {
            const isOpen = openId === faq.id;
            const IconComponent = faq.icon;

            return (
              <div
                key={faq.id}
                className={`bg-white rounded-2xl border transition-all duration-200 overflow-hidden ${
                  isOpen
                    ? 'border-[#2D6A4F] shadow-md ring-1 ring-[#2D6A4F]/10'
                    : 'border-gray-200/90 hover:border-emerald-300 shadow-xs'
                }`}
              >
                <button
                  onClick={() => toggleFaq(faq.id)}
                  className="w-full text-left p-4 sm:p-5 flex items-center justify-between gap-4 focus:outline-none"
                  aria-expanded={isOpen}
                >
                  <div className="flex items-center gap-3 sm:gap-4 pr-2">
                    <div
                      className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                        isOpen
                          ? 'bg-[#1B4332] text-white'
                          : 'bg-emerald-50 text-[#2D6A4F]'
                      }`}
                    >
                      <IconComponent className="w-5 h-5" />
                    </div>
                    <div>
                      <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md mb-1">
                        {faq.category}
                      </span>
                      <h3 className="text-base sm:text-lg font-semibold text-gray-900 leading-snug">
                        {faq.question}
                      </h3>
                    </div>
                  </div>
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-transform duration-300 ${
                      isOpen ? 'bg-emerald-100 text-[#1B4332] rotate-180' : 'bg-gray-50 text-gray-400'
                    }`}
                  >
                    <ChevronDown className="w-4 h-4" />
                  </div>
                </button>

                {isOpen && (
                  <div className="px-4 pb-5 pt-1 sm:px-5 sm:pb-6 text-gray-600 text-sm sm:text-base leading-relaxed border-t border-emerald-50/60 bg-emerald-50/20">
                    <p className="pl-12 sm:pl-14">{faq.answer}</p>
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="text-center py-10 bg-white rounded-2xl border border-dashed border-gray-300">
            <HelpCircle className="w-10 h-10 text-gray-300 mx-auto mb-2" />
            <p className="text-gray-600 font-medium text-sm">No matching questions found.</p>
            <p className="text-gray-400 text-xs mt-1">Try tweaking your search term or selecting "All" categories.</p>
          </div>
        )}
      </div>

      {/* Footer Callout */}
      <div className="mt-10 max-w-3xl mx-auto bg-[#1B4332] rounded-2xl p-6 text-center text-white shadow-md flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-left">
          <h4 className="text-base sm:text-lg font-bold text-white mb-1">Have more questions?</h4>
          <p className="text-xs sm:text-sm text-emerald-100/80">
            Join the platform today to start donating or requesting surplus food.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0 w-full sm:w-auto justify-center">
          <Link
            to="/signup"
            className="px-5 py-2.5 bg-white text-[#1B4332] font-semibold text-xs sm:text-sm rounded-xl hover:bg-emerald-50 transition-colors shadow-xs"
          >
            Get Started Free
          </Link>
        </div>
      </div>
    </section>
  );
};
