import React from 'react';
import { CheckCircle2 } from 'lucide-react';

export function RealBusinessSection() {
  const scenarios = [
    "Customer asks on WhatsApp",
    "Supplier changes price",
    "Stock runs low",
    "Customer forgets payment",
    "Quote is about to expire"
  ];

  return (
    <section className="py-24 bg-white">
      <div className="max-w-[1000px] mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center gap-16">
          
          <div className="flex-1">
            <h2 className="text-[32px] md:text-[40px] font-bold text-[#182235] tracking-tight mb-6 leading-tight">
              Built for the way wholesale actually works.
            </h2>
            <p className="text-[#667085] text-[18px] mb-8 leading-relaxed">
              Business doesn't happen in perfect spreadsheets. It happens in messy WhatsApp chats, sudden price changes, and forgotten payments.
            </p>
            
            <ul className="space-y-4 mb-8">
              {scenarios.map((text, i) => (
                <li key={i} className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-[#5b5bf7]" />
                  <span className="text-[16px] text-[#182235] font-medium">{text}</span>
                </li>
              ))}
            </ul>

            <div className="inline-block px-5 py-3 bg-[#F8FAFF] border border-[#E9E2FF] rounded-xl text-[#5b5bf7] font-bold text-[16px]">
              StockAware keeps the workflow moving.
            </div>
          </div>

          <div className="flex-1 w-full">
            <div className="grid grid-cols-2 gap-4">
               <div className="bg-[#f0f9ff] rounded-2xl p-6 border border-[#bae6fd]">
                  <div className="text-[32px] mb-2">💬</div>
                  <div className="font-bold text-[#0369a1] mb-1">Messy Inputs</div>
                  <div className="text-[13px] text-[#075985]">We turn voice notes into structured orders.</div>
               </div>
               <div className="bg-[#fdf4ff] rounded-2xl p-6 border border-[#e879f9] mt-8">
                  <div className="text-[32px] mb-2">⚡</div>
                  <div className="font-bold text-[#a21caf] mb-1">Fast execution</div>
                  <div className="text-[13px] text-[#86198f]">Quotes generated in seconds, not hours.</div>
               </div>
               <div className="bg-[#f0fdf4] rounded-2xl p-6 border border-[#86efac]">
                  <div className="text-[32px] mb-2">🛡️</div>
                  <div className="font-bold text-[#15803d] mb-1">Margin Safety</div>
                  <div className="text-[13px] text-[#166534]">Never quote below approved margins.</div>
               </div>
               <div className="bg-[#fffbeb] rounded-2xl p-6 border border-[#fcd34d] mt-8">
                  <div className="text-[32px] mb-2">🔗</div>
                  <div className="font-bold text-[#b45309] mb-1">Connected</div>
                  <div className="text-[13px] text-[#92400e]">Quote to invoice without data entry.</div>
               </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
