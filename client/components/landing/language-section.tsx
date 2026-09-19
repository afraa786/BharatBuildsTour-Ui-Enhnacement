'use client'

import { useState } from 'react'
import { ArrowUpRight, Globe2, MessageSquareText, Smartphone } from 'lucide-react'

const whatsappMockup = 'https://img.magnific.com/premium-psd/whatsapp-interface-smartphone-mockup_772836-1128.jpg?semt=ais_hybrid&w=740&q=80'
const languages = ['English', 'हिंदी', 'Hinglish', 'मराठी', 'தமிழ்', 'తెలుగు', 'ગુજરાતી', 'ಕನ್ನಡ']

const showcaseCards = [
  { title: 'WhatsApp-first conversations', description: 'Speak naturally. StockAware understands unstructured voice notes, text messages, and regional languages.', icon: MessageSquareText },
  { title: 'Your language, your way', description: 'Communicate naturally in English, Hindi, Hinglish, Marathi & 10+ languages - including voice replies.', icon: Globe2 },
  { title: 'Ready wherever work happens', description: 'No app downloads required. Keep the familiar WhatsApp experience while StockAware prepares the next action.', icon: Smartphone },
]

export function LanguageSection() {
  const [activeCard, setActiveCard] = useState(0)

  return (
    <section className="relative overflow-hidden bg-[#F7F4ED] px-6 py-24">
      <div className="mx-auto max-w-[1200px]">
        <div className="mb-12 flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <div className="max-w-[650px]">
            <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8FA28A]">The experience stays familiar</p>
            <h2 className="text-[36px] font-bold leading-[1.08] tracking-tight text-[#24302A] md:text-[54px]">Your customers don't have to learn your software.</h2>
            <p className="mt-5 text-[20px] font-semibold text-[#8FA28A]">They can simply talk to your business.</p>
          </div>
          <p className="max-w-[410px] text-[15px] leading-7 text-[#667267]">Speak naturally. StockAware understands unstructured voice notes, text messages, and regional languages. No app downloads required.</p>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="relative min-h-[460px] overflow-hidden rounded-[20px] border border-[#C7D3C0] bg-[#24302A] p-6 shadow-[0_24px_70px_rgba(36,48,42,0.16)] md:p-8">
            <img src={whatsappMockup} alt="WhatsApp conversation on a smartphone" className="absolute inset-0 h-full w-full object-cover opacity-90 transition-transform duration-700 hover:scale-105" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/45 to-transparent" />
            <div className="relative z-10 flex h-full flex-col justify-between">
              <div className="flex items-center justify-between text-white">
                <span className="rounded-full border border-white/30 bg-white/15 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] backdrop-blur-sm">WhatsApp commerce</span>
                <ArrowUpRight className="h-5 w-5" />
              </div>
              <div className="max-w-[430px]">
                <p className="mb-3 font-mono text-[48px] leading-none text-white/50">01</p>
                <h3 className="text-[28px] font-semibold leading-tight text-white">From a voice note to a quote.</h3>
                <p className="mt-3 text-[15px] leading-6 text-white/80">StockAware understands the request, checks stock & pricing, and prepares the quote.</p>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            {showcaseCards.map((card, index) => {
              const Icon = card.icon
              const active = activeCard === index
              return (
                  <button key={card.title} type="button" onMouseEnter={() => setActiveCard(index)} onFocus={() => setActiveCard(index)} className={`group relative flex min-h-[142px] flex-1 overflow-hidden rounded-[16px] border p-6 text-left transition-all duration-500 ${active ? 'border-[#C7D3C0] bg-[#D1D5DB] text-[#24302A] shadow-lg' : 'border-[#C7D3C0] bg-white text-[#24302A] hover:border-[#8FA28A]'}`}>
                  <img src={whatsappMockup} alt="" className={`absolute right-0 top-0 h-full w-1/2 object-cover transition-opacity duration-500 ${active ? 'opacity-25' : 'opacity-10'}`} />
                  <div className="relative z-10 max-w-[390px]">
                    <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl border ${active ? 'border-[#AEB6BC] bg-white/45 text-[#24302A]' : 'border-[#C7D3C0] bg-[#F7F4ED] text-[#8FA28A]'}`}><Icon className="h-5 w-5" /></div>
                    <h3 className="text-[19px] font-semibold leading-tight">{card.title}</h3>
                    <p className={`mt-2 text-[14px] leading-6 ${active ? 'text-[#4B5563]' : 'text-[#667267]'}`}>{card.description}</p>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="mt-8 flex flex-wrap gap-2.5">
          {languages.map((lang) => <span key={lang} className="rounded-full border border-[#C7D3C0] bg-white px-4 py-2 text-[14px] font-medium text-[#24302A] shadow-sm">{lang}</span>)}
          <span className="rounded-full border border-[#C7D3C0] bg-[#C7D3C0]/40 px-4 py-2 text-[14px] font-bold text-[#8FA28A]">+ more</span>
        </div>
      </div>
    </section>
  )
}
