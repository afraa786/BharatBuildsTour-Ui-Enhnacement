import React from 'react';

const workflowSteps = [
  { id: '01', title: 'Customer messages you' },
  { id: '02', title: 'StockAware understands the request' },
  { id: '03', title: 'Stock + pricing checked' },
  { id: '04', title: 'Quote prepared' },
  { id: '05', title: 'Manager approval when required' },
  { id: '06', title: 'Customer receives quote' },
  { id: '07', title: 'Payment link sent' },
  { id: '08', title: 'Invoice generated' },
];

export function WorkflowSection() {
  return (
    <section className="py-24 bg-[#24302A] text-white">
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-[36px] md:text-[44px] font-bold tracking-tight mb-4 text-white">
            From message to money.
          </h2>
          <p className="text-[#94a3b8] text-[18px]">The fully connected WhatsApp workflow.</p>
        </div>

        {/* Desktop Horizontal Workflow */}
        <div className="hidden md:flex flex-wrap justify-center gap-4 relative mt-12">
           {/* Flowing Line Background */}
           <div className="absolute top-[28px] left-[5%] right-[5%] h-px bg-gradient-to-r from-transparent via-[#8FA28A] to-transparent opacity-50"></div>
           
           {workflowSteps.map((step, i) => (
             <div key={i} className="relative z-10 flex flex-col items-center w-[120px] group">
               <div className="w-14 h-14 rounded-2xl bg-[#1e293b] border border-[#334155] flex items-center justify-center text-[18px] font-bold font-mono text-[#cbd5e1] shadow-lg mb-4 group-hover:-translate-y-2 group-hover:bg-[#8FA28A] group-hover:border-[#8FA28A] group-hover:text-white transition-all duration-300">
                 {step.id}
               </div>
               <div className="text-center text-[12px] font-medium text-[#94a3b8] leading-snug group-hover:text-white transition-colors">
                 {step.title}
               </div>
             </div>
           ))}
        </div>

        {/* Mobile Vertical Workflow */}
        <div className="md:hidden flex flex-col gap-6 relative">
          <div className="absolute left-[27px] top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-[#8FA28A] to-transparent opacity-50"></div>
          
          {workflowSteps.map((step, i) => (
             <div key={i} className="relative z-10 flex items-center gap-6 group">
               <div className="w-14 h-14 shrink-0 rounded-2xl bg-[#1e293b] border border-[#334155] flex items-center justify-center text-[18px] font-bold font-mono text-[#cbd5e1] shadow-lg group-hover:bg-[#8FA28A] group-hover:border-[#8FA28A] group-hover:text-white transition-all duration-300">
                 {step.id}
               </div>
               <div className="text-[14px] font-medium text-[#94a3b8] group-hover:text-white transition-colors">
                 {step.title}
               </div>
             </div>
           ))}
        </div>

      </div>
    </section>
  );
}
