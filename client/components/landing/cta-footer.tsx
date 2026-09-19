import React from 'react';
import Link from 'next/link';
import { ArrowRight, MessageSquare } from 'lucide-react';

export function CTAFooter() {
  return (
    <>
      {/* Final CTA Section */}
      <section className="py-24 bg-gradient-to-b from-[#F7F4ED] to-[#C7D3C0] relative overflow-hidden">
        {/* Soft decorative blur */}
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-white rounded-[100%] blur-[80px] opacity-80 pointer-events-none"></div>
        
        <div className="max-w-[800px] mx-auto px-6 text-center relative z-10">
          <h2 className="text-[40px] md:text-[52px] font-bold text-[#24302A] tracking-tight mb-6 leading-tight">
            Let WhatsApp handle<br/>the busywork.
          </h2>
          <p className="text-[18px] md:text-[20px] text-[#667267] leading-relaxed mb-10 max-w-[600px] mx-auto">
            Give your customers instant answers and give yourself a business manager that never forgets.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button className="w-full sm:w-auto px-8 py-4 bg-[#8FA28A] hover:bg-[#7C9178] text-white rounded-full font-semibold text-[16px] shadow-lg shadow-[#8FA28A]/30 transition-all hover:-translate-y-0.5">
              Get Started
            </button>
            <button className="w-full sm:w-auto px-8 py-4 bg-white hover:bg-gray-50 border border-[#C7D3C0] text-[#24302A] rounded-full font-semibold text-[16px] transition-all flex items-center justify-center gap-2 shadow-sm">
              See how it works
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          {/* Mini chat preview subtle decoration */}
          <div className="mt-16 flex justify-center opacity-80 pointer-events-none">
            <div className="bg-white p-4 rounded-2xl shadow-xl shadow-[#24302A]/5 border border-[#C7D3C0] max-w-[300px] text-left">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-100">
                <div className="w-6 h-6 rounded-full bg-[#128c7e] text-white flex items-center justify-center">
                  <MessageSquare className="w-3 h-3" />
                </div>
                <span className="text-[12px] font-semibold text-[#24302A]">StockAware Demo</span>
              </div>
              <div className="bg-[#d9fdd3] p-2 rounded-lg text-[12px] text-gray-800 ml-8 mb-2 relative">
                Hi! Ready to automate your sales?
              </div>
              <div className="bg-[#f0f0f0] p-2 rounded-lg text-[12px] text-gray-800 mr-8 relative">
                Yes, let's go.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer & About Section */}
      <footer className="bg-white border-t border-[#C7D3C0] pt-20 pb-8" id="about">
        <div className="max-w-[1200px] mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10 mb-16">
            
            {/* Brand Column */}
            <div className="lg:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-7 h-7 rounded-lg bg-[#8FA28A] flex items-center justify-center text-white font-bold shadow-sm">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <span className="font-bold text-[18px] tracking-tight text-[#24302A]">StockAware</span>
              </div>
              <p className="text-[14px] text-[#667267] leading-relaxed">
                WhatsApp-first AI operations for wholesale businesses.
              </p>
            </div>

            {/* Product Column */}
            <div>
              <h4 className="font-bold text-[#24302A] text-[14px] mb-4">Product</h4>
              <ul className="space-y-3">
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Sales Agent</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Manager Agent</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">WhatsApp Orders</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Quotes</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Payments</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Invoices</Link></li>
              </ul>
            </div>

            {/* Solutions Column */}
            <div>
              <h4 className="font-bold text-[#24302A] text-[14px] mb-4">Solutions</h4>
              <ul className="space-y-3">
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Wholesale</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Distribution</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Retail</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Customer Follow-ups</Link></li>
              </ul>
            </div>

            {/* Company Column */}
            <div>
              <h4 className="font-bold text-[#24302A] text-[14px] mb-4">Company</h4>
              <ul className="space-y-3">
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">About</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Contact</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Privacy</Link></li>
                <li><Link href="#" className="text-[14px] text-[#667267] hover:text-[#8FA28A]">Terms</Link></li>
              </ul>
            </div>
            
          </div>

          <div className="border-t border-gray-100 pt-8 mb-8">
            <h4 className="font-bold text-[#24302A] text-[14px] mb-2">About StockAware</h4>
            <p className="text-[13px] text-[#667267] max-w-[800px] leading-relaxed">
              StockAware helps wholesale businesses turn everyday WhatsApp conversations into a connected workflow — from customer inquiry and stock checks to quotes, payments, invoices and follow-ups.
            </p>
          </div>

          <div className="border-t border-gray-100 pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-[13px] text-[#667267]">
              &copy; {new Date().getFullYear()} StockAware
            </div>
            <div className="text-[13px] text-[#667267] font-medium">
              Built for businesses that run on WhatsApp.
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
