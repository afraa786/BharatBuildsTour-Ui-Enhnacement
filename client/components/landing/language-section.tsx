import React from 'react';
import { Mic } from 'lucide-react';

export function LanguageSection() {
  const languages = ['English', 'हिंदी', 'Hinglish', 'मराठी', 'தமிழ்', 'తెలుగు', 'ગુજરાતી', 'ಕನ್ನಡ'];

  return (
    <section className="py-24 bg-white relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-white via-[#F8FAFF] to-white opacity-60 z-0"></div>
      
      <div className="max-w-[1000px] mx-auto px-6 relative z-10">
        <div className="flex flex-col md:flex-row items-center gap-12 lg:gap-20">
          
          <div className="flex-1 md:w-1/2">
            <h2 className="text-[32px] md:text-[40px] font-bold text-[#182235] tracking-tight mb-4 leading-tight">
              Your customers don't have to learn your software.
            </h2>
            <p className="text-[20px] text-[#5b5bf7] font-semibold mb-8">
              They can simply talk to your business.
            </p>
            
            <p className="text-[#667085] text-[16px] leading-relaxed mb-8 max-w-[400px]">
              Speak naturally. StockAware understands unstructured voice notes, text messages, and regional languages. No app downloads required.
            </p>

            <div className="flex flex-wrap gap-2.5">
              {languages.map((lang, i) => (
                <div key={i} className="px-4 py-2 bg-white border border-[#E9E2FF] rounded-full text-[14px] font-medium text-[#182235] shadow-sm hover:border-[#5b5bf7]/40 hover:bg-[#F8FAFF] transition-colors cursor-default">
                  {lang}
                </div>
              ))}
              <div className="px-4 py-2 bg-[#F8FAFF] text-[#5b5bf7] border border-[#DFF3FF] rounded-full text-[14px] font-bold shadow-sm">
                + more
              </div>
            </div>
          </div>

          <div className="flex-1 md:w-1/2 w-full max-w-[400px] mt-8 md:mt-0">
            <div className="bg-[#e5ddd5] rounded-[2rem] p-6 shadow-2xl relative">
               <div className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none rounded-[2rem]" 
                   style={{ backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)', backgroundSize: '20px 20px' }} 
              />
              
              <div className="relative z-10 flex flex-col gap-4">
                
                {/* Voice note customer */}
                <div className="flex justify-end">
                   <div className="bg-[#d9fdd3] px-3 py-2 rounded-xl rounded-tr-sm shadow-sm relative min-w-[200px]">
                     <div className="absolute top-0 -right-1.5 w-2 h-2 text-[#d9fdd3]"><svg viewBox="0 0 8 13" fill="currentColor"><path d="M8 0L0 0v13C0 6.5 3.5 1.5 8 0z"/></svg></div>
                     
                     <div className="flex items-center gap-3">
                       <div className="w-8 h-8 rounded-full bg-[#128c7e] text-white flex items-center justify-center">
                         <Mic className="w-4 h-4 fill-current" />
                       </div>
                       <div className="flex-1">
                         <div className="w-full h-[3px] bg-[#128c7e]/20 rounded-full overflow-hidden flex items-center gap-[2px]">
                           {[...Array(15)].map((_, i) => (
                             <div key={i} className="w-[3px] bg-[#128c7e]" style={{ height: `${Math.max(2, Math.random() * 12)}px`, borderRadius: '2px' }}></div>
                           ))}
                         </div>
                       </div>
                       <span className="text-[11px] font-medium text-gray-600">0:12</span>
                     </div>
                   </div>
                </div>

                {/* Agent transcribes/understands */}
                <div className="flex justify-start items-end gap-2 mt-2">
                   <div className="w-6 h-6 rounded-full bg-[#5b5bf7] flex items-center justify-center text-white text-[10px] font-bold shrink-0">SA</div>
                   <div className="bg-white px-3 py-2 rounded-xl rounded-tl-sm text-[13px] text-gray-900 shadow-sm relative max-w-[85%]">
                     <div className="absolute top-0 -left-1.5 w-2 h-2 text-white"><svg viewBox="0 0 8 13" fill="currentColor"><path d="M0 0h8v13C8 6.5 4.5 1.5 0 0z"/></svg></div>
                     <span className="text-[10px] uppercase font-bold text-[#5b5bf7] block mb-1">TRANSLATED: "I want 20 pieces of 32 amp MCB"</span>
                     Got it! We have 8 pieces of 32A MCB in stock right now. I've prepared a quote for what's available.
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
