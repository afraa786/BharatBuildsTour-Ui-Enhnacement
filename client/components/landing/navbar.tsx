import React from 'react';
import Link from 'next/link';

export function Navbar() {
  return (
    <header className="fixed top-0 inset-x-0 z-50 transition-all duration-300 bg-white/70 backdrop-blur-md border-b border-gray-200/50">
      <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between">
        
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#5b5bf7] flex items-center justify-center text-white font-bold text-xl shadow-sm shadow-[#5b5bf7]/30">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-bold text-[19px] tracking-tight text-[#182235]">StockAware</span>
        </div>

        {/* Desktop Links */}
        <nav className="hidden md:flex items-center gap-8">
          <Link href="#product" className="text-[14px] font-medium text-[#667085] hover:text-[#182235] transition-colors">Product</Link>
          <Link href="#how-it-works" className="text-[14px] font-medium text-[#667085] hover:text-[#182235] transition-colors">How it works</Link>
          <Link href="#features" className="text-[14px] font-medium text-[#667085] hover:text-[#182235] transition-colors">Features</Link>
          <Link href="#about" className="text-[14px] font-medium text-[#667085] hover:text-[#182235] transition-colors">About</Link>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-4">
          <Link href="/login" className="hidden sm:block text-[14px] font-medium text-[#667085] hover:text-[#182235] transition-colors">
            Log in
          </Link>
          <Link href="/get-started" className="bg-[#5b5bf7] hover:bg-[#4f4fe6] text-white text-[14px] font-semibold px-4 py-2 rounded-full shadow-sm shadow-[#5b5bf7]/20 transition-all hover:-translate-y-0.5">
            Get Started
          </Link>
        </div>

      </div>
    </header>
  );
}
