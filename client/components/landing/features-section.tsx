'use client'

import { useState } from 'react'
import { Box, CreditCard, Globe, MessageSquare, BellRing } from 'lucide-react'

const features = [
  { icon: MessageSquare, title: 'WhatsApp Orders \u2192 Instant Quotes', description: 'Customers send their requirements on WhatsApp. StockAware understands the request, checks stock & pricing, and prepares the quote.', image: 'https://img.magnific.com/premium-psd/whatsapp-interface-smartphone-mockup_772836-1128.jpg?semt=ais_hybrid&w=740&q=80', background: 'linear-gradient(145deg, #8FA28A, #52684F)' },
  { icon: Globe, title: 'Speak Your Language \u2014 10+ Languages', description: 'Communicate naturally in English, Hindi, Hinglish, Marathi & 10+ languages \u2014 including voice replies. No complicated software training.', image: 'https://cdn.dribbble.com/userupload/15700965/file/original-2af8a595f1480808eb7a6d7159d57c62.png?crop=0x0-3201x2401&format=webp&resize=400x300&vertical=center', background: 'linear-gradient(145deg, #C8A96B, #8F7741)' },
  { icon: Box, title: 'Know Your Stock Before You Promise', description: 'Get instant visibility into available, low-stock & out-of-stock items, helping you avoid overpromising and missed orders.', image: 'https://d2pas86kykpvmq.cloudfront.net/uploads/glass_cards_preview_1_2a4597d7f9.png', background: 'linear-gradient(145deg, #C7D3C0, #738871)' },
  { icon: CreditCard, title: 'From Quote \u2192 Payment \u2192 Invoice', description: 'Turn approved quotes into payment links and invoices in one connected workflow \u2014 fewer manual steps, faster order processing.', image: 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTW9JNUXkSbAijty9ONrG4FstieqrYF_ruBCxd35eFFDQ&s', background: 'linear-gradient(145deg, #52684F, #24302A)' },
  { icon: BellRing, title: 'Never Miss a Follow-Up or Important Update', description: 'Get alerts for pending payments, low stock, expiring quotes, vendor price changes, shortages and customer follow-ups - all in one Manager control room.', image: 'https://plus.unsplash.com/premium_photo-1683120966127-14162cdd0935?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NXx8dGVjaG5vbG9neXxlbnwwfHwwfHx8MA%3D%3D', background: 'linear-gradient(145deg, #8F7741, #C8A96B)' },
]

export function FeaturesSection() {
  const [activeIndex, setActiveIndex] = useState(0)

  return (
    <section id="features" className="bg-[#F7F4ED] px-6 py-24">
      <div className="mx-auto max-w-[1200px]">
        <div className="mb-10 flex flex-col justify-between gap-2 lg:flex-row lg:items-end">
          <div>
            <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8FA28A]">A calmer operating layer</p>
            <h2 className="max-w-[620px] text-[34px] font-bold leading-tight tracking-tight text-[#24302A] md:text-[48px]">Your business runs on WhatsApp. StockAware makes it work harder.</h2>
          </div>
          <p className="max-w-[420px] text-[15px] leading-7 text-[#667267]">Five connected experiences that turn everyday conversations into confident business decisions.</p>
        </div>

        <div className="flex w-full flex-col gap-3 pb-4 md:h-[580px] md:flex-row">
          {features.map((feature, index) => {
            const Icon = feature.icon
            const isActive = activeIndex === index
            const number = String(index + 1).padStart(2, '0')

            return (
              <article
                key={feature.title}
                tabIndex={0}
                aria-expanded={isActive}
                onMouseEnter={() => setActiveIndex(index)}
                onFocus={() => setActiveIndex(index)}
                className={`group relative min-h-[150px] overflow-hidden rounded-[16px] transition-all duration-500 ease-in-out md:min-h-0 md:shrink-0 ${isActive ? 'md:w-[360px] max-md:h-[300px]' : 'md:w-[188px] max-md:h-[150px]'} focus:outline-none focus:ring-2 focus:ring-[#C8A96B]`}
                style={{ background: feature.background }}
              >
                <img src={feature.image} alt="" className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105" />
                <div className="absolute inset-0 z-10 bg-black/50" aria-hidden="true" />
                <div className="absolute inset-0 z-10 bg-gradient-to-t from-black/85 via-black/35 to-transparent" aria-hidden="true" />

                <div className={`absolute inset-x-0 z-20 flex flex-col gap-3 px-6 transition-all duration-500 ${isActive ? 'bottom-7 opacity-100' : 'pointer-events-none bottom-5 opacity-0'}`}>
                  <p className="font-mono text-[48px] leading-none tracking-[0.08em] text-white/50">{number}</p>
                  <div>
                    <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-white/30 bg-white/15 text-white backdrop-blur-sm"><Icon className="h-5 w-5" /></div>
                    <h3 className="text-[22px] font-semibold leading-tight text-white">{feature.title}</h3>
                    <p className="mt-2 text-[14px] leading-6 text-white/85">{feature.description}</p>
                  </div>
                </div>

                <div className={`absolute bottom-6 left-1/2 z-20 -translate-x-1/2 transition-all duration-500 ${isActive ? 'pointer-events-none opacity-0' : 'opacity-100'}`}>
                  <div className="flex items-center gap-2 md:flex-col">
                    <span className="font-mono text-[62px] leading-none tracking-[0.08em] text-white/20 md:[writing-mode:sideways-lr]">{number}</span>
                    <span className="whitespace-nowrap text-[20px] font-semibold text-white/70 md:[writing-mode:sideways-lr]">{feature.title}</span>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}

