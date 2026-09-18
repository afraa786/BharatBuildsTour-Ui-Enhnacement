import React from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ChatBubbleProps {
  role: 'customer' | 'agent' | 'system';
  children: React.ReactNode;
  time?: string;
  className?: string;
  isManager?: boolean;
}

export function ChatBubble({ role, children, time, className, isManager }: ChatBubbleProps) {
  if (role === 'system') {
    return (
      <div className={cn("flex justify-center my-2", className)}>
        <span className="text-[10px] bg-[#E1F0FA] text-[#4a5568] px-2 py-0.5 rounded-md font-medium shadow-sm">
          {children}
        </span>
      </div>
    );
  }

  // Manager Theme Bubble
  if (isManager) {
     return (
        <div className={cn("flex flex-col mb-3 animate-in fade-in slide-in-from-bottom-2 duration-500", className)}>
          {role === 'agent' ? (
             <div className="flex gap-2.5 items-end">
               <div className="w-6 h-6 rounded-full bg-[#5b5bf7] flex-shrink-0 flex items-center justify-center text-white text-xs font-bold shadow-md shadow-[#5b5bf7]/30">
                 SA
               </div>
               <div className="bg-white border border-[#E9E2FF] text-[#182235] px-3.5 py-2.5 rounded-2xl rounded-bl-sm text-[13px] shadow-sm max-w-[85%] leading-snug">
                 {children}
               </div>
             </div>
          ) : (
             <div className="flex justify-end mb-1">
               <div className="bg-[#E9E2FF] text-[#182235] px-3.5 py-2.5 rounded-2xl rounded-br-sm text-[13px] shadow-sm max-w-[85%] leading-snug">
                 {children}
               </div>
             </div>
          )}
        </div>
     );
  }

  // Sales (WhatsApp-like) Theme Bubble
  const isCustomer = role === 'customer';
  return (
    <div className={cn(
      "flex flex-col mb-1 animate-in fade-in slide-in-from-bottom-2 duration-500",
      isCustomer ? "items-end" : "items-start",
      className
    )}>
      <div className={cn(
        "relative px-2.5 py-1.5 rounded-lg text-[13px] shadow-sm max-w-[85%] leading-snug text-gray-900",
        isCustomer ? "bg-[#d9fdd3] rounded-tr-sm" : "bg-white rounded-tl-sm"
      )}>
        {/* Tail */}
        <div className={cn(
          "absolute top-0 w-3 h-3",
          isCustomer ? "-right-[6px] text-[#d9fdd3]" : "-left-[6px] text-white"
        )}>
          <svg viewBox="0 0 8 13" fill="currentColor"><path d={isCustomer ? "M8 0L0 0v13C0 6.5 3.5 1.5 8 0z" : "M0 0h8v13C8 6.5 4.5 1.5 0 0z"}/></svg>
        </div>
        
        <div className="relative z-10 pb-3">
           {children}
        </div>
        
        <div className="absolute right-2 bottom-1 flex items-center gap-1 z-10">
          <span className="text-[9px] text-gray-500 font-medium">{time || '10:42 AM'}</span>
          {isCustomer && (
            <svg className="w-3 h-3 text-[#53bdeb]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7M5 13l4 4L19 7" style={{transform: 'translateX(-4px)'}} />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M11 13l4 4L23 7" style={{transform: 'translateX(-4px)'}} />
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}

export function QuoteCard({ quantity, product, total }: { quantity: number, product: string, total: string }) {
  return (
    <div className="bg-[#f0f2f5] border border-gray-200 rounded-md p-2.5 mt-2 mb-1 shadow-sm w-full">
      <div className="font-semibold text-[13px] text-gray-900 border-b border-gray-300 pb-1.5 mb-1.5">Quote Prepared</div>
      <div className="flex justify-between text-xs text-gray-700 mb-1">
        <span>{quantity} × {product}</span>
        <span className="font-medium">{total}</span>
      </div>
      <div className="flex justify-between text-xs text-gray-700 mb-2">
        <span>Delivery</span>
        <span>Included</span>
      </div>
      <div className="flex justify-between text-[13px] font-bold text-gray-900 border-t border-gray-300 pt-1.5 mb-2.5">
        <span>Total</span>
        <span>{total}</span>
      </div>
      <button className="w-full py-1.5 bg-white border border-gray-300 rounded font-medium text-[12px] text-gray-800 hover:bg-gray-50 transition-colors">
        Review Quote
      </button>
    </div>
  );
}

export function PaymentCard({ total }: { total: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-md p-2.5 mt-2 mb-1 shadow-sm w-full text-center">
      <div className="text-xs text-gray-500 font-medium mb-0.5">Amount to pay</div>
      <div className="font-bold text-xl text-gray-900 mb-3">{total}</div>
      <button className="w-full py-2 bg-[#3395ff] rounded font-semibold text-[13px] text-white flex items-center justify-center gap-1.5 hover:bg-blue-600 transition-colors shadow-sm">
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
        Pay Securely
      </button>
      <div className="text-[9px] text-gray-400 mt-2 font-medium tracking-wide uppercase">Secured by Razorpay</div>
    </div>
  );
}

export function ManagerCard({ icon, title, value, variant = 'default' }: { icon: string, title: string, value: React.ReactNode, variant?: 'default' | 'alert' | 'success' }) {
  return (
    <div className="bg-white border border-[#E9E2FF] rounded-xl p-3 shadow-sm w-full flex items-start gap-3 mt-1.5">
       <div className={cn(
         "w-8 h-8 rounded-full flex items-center justify-center text-[15px] shrink-0",
         variant === 'alert' ? 'bg-[#fff3f3] text-[#e02424]' : 
         variant === 'success' ? 'bg-[#f3faf7] text-[#059669]' : 
         'bg-[#f4f7ff] text-[#5b5bf7]'
       )}>
         {icon}
       </div>
       <div className="flex flex-col">
         <span className="text-[11px] font-medium text-[#667085]">{title}</span>
         <span className={cn("text-[13px] font-semibold mt-0.5 leading-snug", variant === 'alert' ? 'text-[#e02424]' : 'text-[#182235]')}>{value}</span>
       </div>
    </div>
  );
}

export function ActionButtons({ primary, secondary }: { primary: string, secondary?: string }) {
  return (
    <div className="flex gap-2 w-full mt-2">
      <button className="flex-1 py-1.5 bg-[#5b5bf7] text-white text-[11px] font-semibold rounded-full shadow-sm shadow-[#5b5bf7]/20 hover:opacity-90 transition-opacity">
        {primary}
      </button>
      {secondary && (
        <button className="flex-1 py-1.5 bg-white border border-[#E9E2FF] text-[#182235] text-[11px] font-medium rounded-full shadow-sm hover:bg-gray-50 transition-colors">
          {secondary}
        </button>
      )}
    </div>
  );
}
