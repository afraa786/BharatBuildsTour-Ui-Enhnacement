import React from 'react';

export function TwoAgentsSection() {
  return (
    <section className="pb-24 pt-36 bg-[#F7F4ED] border-y border-[#C7D3C0]/60 overflow-hidden">
      <div className="max-w-[1200px] mx-auto px-6 relative">
        <div className="mb-20 flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <div>
            <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8FA28A]">CONNECTED AI WORKFLOW</p>
            <h2 className="text-left text-[36px] font-bold leading-tight tracking-tight text-[#24302A] md:text-[52px]">
              Two AI agents.<br/>
              One business running smoothly.
            </h2>
          </div>
          <p className="max-w-[430px] text-left text-[15px] leading-7 text-[#667267] lg:text-right">Your sales and manager agents work together to turn customer conversations into confident business decisions.</p>
        </div>

        <div className="relative flex flex-col md:flex-row items-stretch justify-between gap-12 lg:gap-24">
          
          {/* Connector Line (Desktop) */}
          <div className="hidden md:block absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[2px] bg-gradient-to-b from-transparent via-[#BFE7FF] to-transparent">
             <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-[#8FA28A] shadow-[0_0_15px_rgba(91,91,247,0.5)]"></div>
             <div className="absolute top-3/4 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-[#8FA28A] shadow-[0_0_15px_rgba(91,91,247,0.5)]"></div>
          </div>

          {/* Manager Agent Column */}
          <div className="flex-1 relative z-10 flex flex-col pt-12 md:order-2 md:pt-0">
            <div className="mb-8">
              <div className="inline-block px-3 py-1 bg-white border border-[#F3B5B5] rounded-full text-[12px] font-bold text-[#DC2626] uppercase tracking-wider mb-4 shadow-sm">
                Manager Agent
              </div>
              <h3 className="text-[22px] font-bold text-[#24302A] mb-3 leading-tight">Your business briefing, without opening another dashboard.</h3>
            </div>

            <div className="relative rounded-[18px] border border-[#303A35] bg-[#202824] p-3 pb-5 shadow-[0_28px_50px_rgba(36,48,42,0.32)]">
              <div className="mb-3 flex h-7 items-center rounded-t-[10px] bg-[#121815] px-3 shadow-inner">
                <div className="flex gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" /></div>
                <div className="mx-auto h-1.5 w-16 rounded-full bg-[#667267]" />
              </div>
              <div className="flex flex-col gap-3 rounded-[10px] border border-[#C7D3C0] bg-white p-6">
              <div className="bg-[#F7F4ED] p-4 rounded-xl border border-[#C7D3C0]">
                <div className="text-[14px] font-medium text-[#24302A] mb-1">Good morning, Aamir 👋</div>
                <div className="text-[13px] text-[#667267]">Here's what needs your attention today.</div>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-2">
                <div className="bg-white border border-gray-100 p-3 rounded-lg shadow-sm">
                  <div className="text-[11px] text-[#667267] font-medium mb-1 uppercase tracking-wider">Sales Yesterday</div>
                  <div className="text-[16px] font-bold text-[#059669]">₹1.84L</div>
                </div>
                <div className="bg-[#fff3f3] border border-[#fecaca] p-3 rounded-lg shadow-sm">
                  <div className="text-[11px] text-[#e02424] font-medium mb-1 uppercase tracking-wider">Low Stock</div>
                  <div className="text-[13px] font-semibold text-[#24302A]">MCB32 <span className="font-normal text-gray-500">(8 left)</span></div>
                </div>
              </div>

              <div className="space-y-2 mt-2">
                <div className="flex items-center justify-between p-3 bg-white border border-gray-100 rounded-lg shadow-sm">
                   <div className="flex items-center gap-2">
                     <span className="w-2 h-2 rounded-full bg-[#f59e0b]"></span>
                     <span className="text-[13px] font-medium text-[#24302A]">3 Pending Payments</span>
                   </div>
                   <span className="text-[13px] font-bold text-[#667267]">₹42,500</span>
                </div>
                <div className="flex items-center justify-between p-3 bg-white border border-gray-100 rounded-lg shadow-sm">
                   <div className="flex items-center gap-2">
                     <span className="w-2 h-2 rounded-full bg-[#38bdf8]"></span>
                     <span className="text-[13px] font-medium text-[#24302A]">MCB32 vendor price updated</span>
                   </div>
                </div>
              </div>
              </div>
            </div>
          </div>

          {/* Sales Agent Column */}
          <div className="flex-1 relative z-10 flex flex-col md:order-1 md:pt-0">
            <div className="mb-8">
              <div className="inline-block px-3 py-1 bg-white border border-[#C7D3C0] rounded-full text-[12px] font-bold text-[#059669] uppercase tracking-wider mb-4 shadow-sm">
                Sales Agent
              </div>
              <h3 className="text-[22px] font-bold text-[#24302A] mb-3 leading-tight">Your customers get instant answers, quotes and payment links.</h3>
            </div>

            <div className="relative rounded-[18px] border border-[#303A35] bg-[#202824] p-3 pb-5 shadow-[0_28px_50px_rgba(36,48,42,0.32)]">
              <div className="mb-3 flex h-7 items-center rounded-t-[10px] bg-[#121815] px-3 shadow-inner">
                <div className="flex gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" /></div>
                <div className="mx-auto h-1.5 w-16 rounded-full bg-[#667267]" />
              </div>
              <div className="relative min-h-[290px] overflow-hidden rounded-[10px] border-8 border-white bg-[#e5ddd5] p-4">
               {/* Chat Background Pattern Simulation */}
              <div className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none" 
                   style={{ backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)', backgroundSize: '20px 20px' }} 
              />
              
              <div className="relative z-10 flex flex-col gap-2 h-full">
                {/* Flow lines overlay */}
                <div className="absolute -left-6 top-6 bottom-6 w-px bg-gradient-to-b from-transparent via-[#059669] to-transparent opacity-30"></div>

                <div className="flex flex-col items-end animate-in fade-in slide-in-from-bottom-2">
                  <span className="text-[10px] text-gray-500 font-medium mb-1">Customer</span>
                  <div className="bg-[#d9fdd3] px-3 py-2 rounded-xl rounded-tr-sm text-[13px] text-gray-900 shadow-sm relative">
                    Need 20 MCB
                    <div className="absolute top-0 -right-1.5 w-2 h-2 text-[#d9fdd3]"><svg viewBox="0 0 8 13" fill="currentColor"><path d="M8 0L0 0v13C0 6.5 3.5 1.5 8 0z"/></svg></div>
                  </div>
                </div>

                <div className="flex flex-col items-start mt-2">
                  <span className="text-[10px] text-gray-500 font-medium mb-1 flex items-center gap-1">
                     <svg className="w-3 h-3 text-[#8FA28A]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                     Stock Check
                  </span>
                  <div className="bg-white/80 backdrop-blur px-3 py-2 rounded-xl text-[12px] text-gray-600 font-mono shadow-sm border border-gray-100">
                    Querying inventory: MCB32... 8 available.
                  </div>
                </div>

                <div className="flex flex-col items-start mt-2">
                  <span className="text-[10px] text-[#059669] font-medium mb-1 flex items-center gap-1">
                     <span className="w-1.5 h-1.5 bg-[#059669] rounded-full"></span>
                     Sales Agent
                  </span>
                  <div className="bg-white px-3 py-2 rounded-xl rounded-tl-sm text-[13px] text-gray-900 shadow-sm relative">
                    We only have 8 in stock. Quote ready for 8 pieces: ₹3,600
                    <div className="absolute top-0 -left-1.5 w-2 h-2 text-white"><svg viewBox="0 0 8 13" fill="currentColor"><path d="M0 0h8v13C8 6.5 4.5 1.5 0 0z"/></svg></div>
                  </div>
                </div>

                <div className="mt-2 w-full">
                  <div className="bg-[#3395ff] text-white rounded-lg p-2.5 text-center shadow-sm">
                     <span className="block text-[10px] opacity-80 uppercase tracking-wider mb-0.5">Payment Link Sent</span>
                     <span className="font-bold text-[14px]">₹3,600</span>
                  </div>
                </div>

              </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
