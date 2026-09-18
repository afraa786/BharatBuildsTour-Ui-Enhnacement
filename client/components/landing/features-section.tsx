import React from 'react';
import { MessageSquare, Globe, Box, CreditCard, BellRing } from 'lucide-react';

const features = [
  {
    icon: <MessageSquare className="w-5 h-5 text-[#5b5bf7]" />,
    title: "WhatsApp Orders → Instant Quotes",
    description: "Customers send their requirements on WhatsApp. StockAware understands the request, checks stock & pricing, and prepares the quote."
  },
  {
    icon: <Globe className="w-5 h-5 text-[#059669]" />,
    title: "Speak Your Language — 10+ Languages",
    description: "Communicate naturally in English, Hindi, Hinglish, Marathi & 10+ languages — including voice replies. No complicated software training."
  },
  {
    icon: <Box className="w-5 h-5 text-[#f59e0b]" />,
    title: "Know Your Stock Before You Promise",
    description: "Get instant visibility into available, low-stock & out-of-stock items, helping you avoid overpromising and missed orders."
  },
  {
    icon: <CreditCard className="w-5 h-5 text-[#8b5cf6]" />,
    title: "From Quote → Payment → Invoice",
    description: "Turn approved quotes into payment links and invoices in one connected workflow — fewer manual steps, faster order processing."
  },
  {
    icon: <BellRing className="w-5 h-5 text-[#e02424]" />,
    title: "Never Miss a Follow-Up or Important Update",
    description: "Get alerts for pending payments, low stock, expiring quotes, vendor price changes, shortages and customer follow-ups — all in one Manager control room."
  }
];

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 bg-white">
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="text-center max-w-[700px] mx-auto mb-16">
          <h2 className="text-[32px] md:text-[40px] font-bold text-[#182235] tracking-tight mb-4 leading-tight">
            Your business runs on WhatsApp.<br/>
            StockAware makes it work harder.
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <div 
              key={i} 
              className={`p-8 rounded-2xl bg-[#F8FAFF] border border-[#E9E2FF] hover:shadow-lg hover:shadow-[#5b5bf7]/5 transition-all duration-300 hover:-translate-y-1 group ${
                i === 3 || i === 4 ? 'lg:col-span-1.5' : ''
              }`}
              style={
                (i === 3 || i === 4) && typeof window !== 'undefined' && window.innerWidth >= 1024 
                ? { gridColumn: i === 3 ? '1 / span 1' : '2 / span 2' } 
                : {}
              }
            >
              <div className="w-12 h-12 rounded-xl bg-white border border-[#E9E2FF] shadow-sm flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                {feature.icon}
              </div>
              <h3 className="text-[19px] font-bold text-[#182235] mb-3 leading-tight">{feature.title}</h3>
              <p className="text-[#667085] text-[15px] leading-relaxed">
                {feature.description}
              </p>
              
              {/* Visual augmentations based on feature index */}
              {i === 2 && (
                <div className="mt-6 flex flex-wrap gap-2">
                   <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#dff8ed] text-[#059669] text-[11px] font-bold font-mono"><span className="w-1.5 h-1.5 rounded-full bg-[#059669]"></span>IN STOCK</span>
                   <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#fff3d7] text-[#b45309] text-[11px] font-bold font-mono"><span className="w-1.5 h-1.5 rounded-full bg-[#b45309]"></span>LOW STOCK</span>
                   <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#fee2e2] text-[#dc2626] text-[11px] font-bold font-mono"><span className="w-1.5 h-1.5 rounded-full bg-[#dc2626]"></span>OUT OF STOCK</span>
                </div>
              )}
              {i === 3 && (
                <div className="mt-6 flex items-center gap-3 text-[12px] font-semibold text-[#667085]">
                   <span className="bg-white px-3 py-1.5 rounded-lg border border-[#E9E2FF] shadow-sm text-[#182235]">Quote</span>
                   <span>→</span>
                   <span className="bg-white px-3 py-1.5 rounded-lg border border-[#E9E2FF] shadow-sm text-[#182235]">Approval</span>
                   <span>→</span>
                   <span className="bg-white px-3 py-1.5 rounded-lg border border-[#E9E2FF] shadow-sm text-[#182235]">Payment</span>
                   <span>→</span>
                   <span className="bg-white px-3 py-1.5 rounded-lg border border-[#E9E2FF] shadow-sm text-[#182235]">Invoice</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
