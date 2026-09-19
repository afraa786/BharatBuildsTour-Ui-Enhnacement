import React from 'react';
import { AlertCircle, CreditCard, Clock, TrendingUp, UserCheck } from 'lucide-react';

export function ControlRoomPreview() {
  return (
    <section className="py-24 bg-[#F7F4ED]">
      <div className="max-w-[1000px] mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-[32px] md:text-[40px] font-bold text-[#24302A] tracking-tight mb-4">
            Know what needs your attention.
          </h2>
          <p className="text-[#667267] text-[18px]">
            The manager sees only what matters. No cluttered dashboards.
          </p>
        </div>

        <div className="bg-white rounded-[2rem] border border-[#C7D3C0] shadow-2xl p-4 md:p-8 relative overflow-hidden">
           {/* Soft glow in the background of the dashboard */}
           <div className="absolute top-0 right-0 w-64 h-64 bg-[#C7D3C0] rounded-full blur-[80px] opacity-50 -z-10 pointer-events-none"></div>

           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              
              {/* Card 1 */}
              <div className="bg-white border border-[#fecaca] rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-[#fff3f3] text-[#e02424] flex items-center justify-center">
                    <AlertCircle className="w-5 h-5" />
                  </div>
                  <div className="text-[12px] font-bold tracking-wider text-[#e02424] uppercase">Low Stock</div>
                </div>
                <div className="text-[18px] font-bold text-[#24302A] mb-1">MCB32</div>
                <div className="text-[14px] text-[#667267]">8 units remaining</div>
              </div>

              {/* Card 2 */}
              <div className="bg-white border border-[#fed7aa] rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-[#fff7ed] text-[#f97316] flex items-center justify-center">
                    <CreditCard className="w-5 h-5" />
                  </div>
                  <div className="text-[12px] font-bold tracking-wider text-[#f97316] uppercase">Pending Payment</div>
                </div>
                <div className="text-[18px] font-bold text-[#24302A] mb-1">3 customers</div>
                <div className="text-[14px] text-[#667267]">₹42,500 outstanding</div>
              </div>

              {/* Card 3 */}
              <div className="bg-white border border-[#e2e8f0] rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-[#f8fafc] text-[#64748b] flex items-center justify-center">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div className="text-[12px] font-bold tracking-wider text-[#64748b] uppercase">Expiring Quotes</div>
                </div>
                <div className="text-[18px] font-bold text-[#24302A] mb-1">2 quotes</div>
                <div className="text-[14px] text-[#667267]">Expiring today</div>
              </div>

              {/* Card 4 */}
              <div className="bg-white border border-[#bfdbfe] rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-[#eff6ff] text-[#3b82f6] flex items-center justify-center">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <div className="text-[12px] font-bold tracking-wider text-[#3b82f6] uppercase">Vendor Update</div>
                </div>
                <div className="text-[16px] font-bold text-[#24302A] mb-1 leading-snug">MCB32 price revised</div>
                <div className="text-[14px] text-[#667267]">Review new margins</div>
              </div>

              {/* Card 5 */}
              <div className="bg-white border border-[#d8b4fe] rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow lg:col-span-2">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-[#faf5ff] text-[#a855f7] flex items-center justify-center">
                    <UserCheck className="w-5 h-5" />
                  </div>
                  <div className="text-[12px] font-bold tracking-wider text-[#a855f7] uppercase">Customer Follow-Up</div>
                </div>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="text-[18px] font-bold text-[#24302A] mb-1">5 follow-ups due</div>
                    <div className="text-[14px] text-[#667267]">Sent quotes without replies in 48h</div>
                  </div>
                  <button className="px-5 py-2.5 bg-[#a855f7] text-white rounded-xl text-[14px] font-semibold shadow-sm hover:bg-[#9333ea] transition-colors whitespace-nowrap">
                    Review Follow-ups
                  </button>
                </div>
              </div>

           </div>
        </div>
      </div>
    </section>
  );
}
